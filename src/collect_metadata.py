"""Database metadata collection script for PostgreSQL/TimescaleDB -> SQLite."""

import os
import sqlite3
from datetime import datetime, timezone
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# 스크립트 위치 기준 경로 설정
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
load_dotenv(dotenv_path=PROJECT_DIR / ".env")

LOCAL_DB_PATH = SCRIPT_DIR / "db_monitoring.sqlite"

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _sqlite_init(conn: sqlite3.Connection):
    # 1. 메인 테이블 정보 (하이퍼테이블 & 일반 테이블) - 대시보드 표시용
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            name TEXT,
            schema_name TEXT,
            table_type TEXT,
            actual_rows INTEGER,
            is_compressed BOOLEAN DEFAULT FALSE,
            table_size INTEGER
        )
    """)
    
    # 2. 청크 정보 별도 분리 - 상세 분석용 (대시보드 합산 제외)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_name TEXT,
            schema_name TEXT,
            hypertable_name TEXT,
            actual_rows INTEGER,
            is_compressed BOOLEAN DEFAULT FALSE,
            table_size INTEGER
        )
    """)

    # 3. 로그 테이블 (메인 테이블 기준 이력)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS table_logs (
            table_name TEXT,
            schema_name TEXT,
            date TEXT,
            row_count INTEGER,
            table_size INTEGER,
            sample_count INTEGER DEFAULT 1
        )
    """)

    # Migration: Add sample_count column if it doesn't exist
    try:
        conn.execute("ALTER TABLE table_logs ADD COLUMN sample_count INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # 4. 실행 정보
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_info (
            collected_at TEXT,
            mode TEXT,
            db_host TEXT,
            db_name TEXT
        )
    """)

def _require_env(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"Missing required env: {key}")
    return v

def _get_prod_db_config():
    return {
        "host": _require_env("PROD_DB_HOST"),
        "port": int(os.getenv("PROD_DB_PORT", "5432")),
        "database": _require_env("PROD_DB_NAME"),
        "user": _require_env("PROD_DB_USER"),
        "password": _require_env("PROD_DB_PASSWORD"),
    }

def collect_prod_data():
    cfg = _get_prod_db_config()

    sqlite_conn = sqlite3.connect(LOCAL_DB_PATH)
    _sqlite_init(sqlite_conn)

    pg = psycopg2.connect(**cfg)
    pg.autocommit = True
    cur = pg.cursor()

    tables_data = [] # 하이퍼테이블 + 일반테이블 (대시보드용)
    chunks_data = [] # 청크 (분석용, 별도 저장)

    print("Connected to DB. Starting collection...")

    # 1) Timescale chunks 수집 -> 'chunks' 테이블로 분리
    try:
        cur.execute("""
            SELECT
              chunk_schema,
              chunk_name,
              hypertable_name,
              is_compressed
            FROM timescaledb_information.chunks
            WHERE chunk_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        chunk_rows = cur.fetchall()

        for schema, name, hypertable, is_compressed in chunk_rows:
            cur.execute("""
                SELECT
                  COALESCE(c.reltuples::bigint, 0) AS est_rows,
                  pg_total_relation_size(%s::regclass) AS bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
                LIMIT 1
            """, (f"{schema}.{name}", schema, name))
            r = cur.fetchone()
            if not r:
                continue
            est_rows, bytes_ = int(r[0] or 0), int(r[1] or 0)
            
            # chunks 리스트에 저장
            chunks_data.append((name, schema, hypertable, est_rows, bool(is_compressed), bytes_))
    except Exception as e:
        print(f"Warning: Failed to collect chunks (TimescaleDB might not be active): {e}")

    # 2) Hypertables (있으면) -> 'tables' 테이블에 저장
    # hypertable_size()를 사용하여 이미 모든 청크 용량이 포함됨
    hypertables = set()
    try:
        cur.execute("""
            SELECT hypertable_schema, hypertable_name, compression_enabled
            FROM timescaledb_information.hypertables
            WHERE hypertable_schema NOT IN ('pg_catalog','information_schema')
        """)
        for schema, name, compression_enabled in cur.fetchall():
            hypertables.add((schema, name))
            
            cur.execute("""
                SELECT
                  COALESCE(c.reltuples::bigint, 0) AS est_rows,
                  hypertable_size(%s::regclass) AS bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
                LIMIT 1
            """, (f"{schema}.{name}", schema, name))
            r = cur.fetchone()
            if not r:
                continue
            est_rows, bytes_ = int(r[0] or 0), int(r[1] or 0)
            
            # tables 리스트에 저장
            tables_data.append((name, schema, "hypertable", est_rows, bool(compression_enabled), bytes_))
    except Exception as e:
        print(f"Warning: Failed to collect hypertables: {e}")

    # 3) Regular tables (chunks/hypertables 제외) -> 'tables' 테이블에 저장
    try:
        cur.execute("""
            SELECT n.nspname, c.relname,
                   COALESCE(c.reltuples::bigint, 0) AS est_rows,
                   pg_total_relation_size((quote_ident(n.nspname)||'.'||quote_ident(c.relname))::regclass) AS bytes
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog','information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
              AND n.nspname NOT LIKE '_timescaledb_%'
        """)
        for schema, name, est_rows, bytes_ in cur.fetchall():
            if (schema, name) in hypertables:
                continue
            tables_data.append((name, schema, "table", int(est_rows or 0), False, int(bytes_ or 0)))
    except Exception as e:
        print(f"Warning: Failed to collect regular tables: {e}")

    # --- Write to SQLite ---

    # A. tables 테이블 갱신 (하이퍼테이블 + 일반테이블)
    sqlite_conn.execute("DELETE FROM tables")
    sqlite_conn.executemany(
        "INSERT INTO tables(name, schema_name, table_type, actual_rows, is_compressed, table_size) VALUES (?, ?, ?, ?, ?, ?)",
        tables_data
    )

    # B. chunks 테이블 갱신 (청크 데이터 별도 저장)
    sqlite_conn.execute("DELETE FROM chunks")
    sqlite_conn.executemany(
        "INSERT INTO chunks(chunk_name, schema_name, hypertable_name, actual_rows, is_compressed, table_size) VALUES (?, ?, ?, ?, ?, ?)",
        chunks_data
    )

    # C. logs snapshot (tables_data 기준만 저장 - 일 평균 계산)
    today = datetime.now().strftime("%Y-%m-%d")

    for name, schema, _, rows, _, size in tables_data:
        # 기존 데이터 확인
        cursor = sqlite_conn.execute(
            "SELECT row_count, table_size, sample_count FROM table_logs WHERE table_name = ? AND schema_name = ? AND date = ?",
            (name, schema, today)
        )
        existing = cursor.fetchone()

        if existing:
            # 평균 계산: new_avg = (old_avg * old_count + new_value) / (old_count + 1)
            old_rows, old_size, old_count = existing
            new_count = old_count + 1
            new_avg_rows = int((old_rows * old_count + rows) / new_count)
            new_avg_size = int((old_size * old_count + size) / new_count)

            sqlite_conn.execute(
                "UPDATE table_logs SET row_count = ?, table_size = ?, sample_count = ? WHERE table_name = ? AND schema_name = ? AND date = ?",
                (new_avg_rows, new_avg_size, new_count, name, schema, today)
            )
        else:
            # 새로 삽입
            sqlite_conn.execute(
                "INSERT INTO table_logs(table_name, schema_name, date, row_count, table_size, sample_count) VALUES (?, ?, ?, ?, ?, ?)",
                (name, schema, today, rows, size, 1)
            )

    # D. run_info
    sqlite_conn.execute("DELETE FROM run_info")
    sqlite_conn.execute(
        "INSERT INTO run_info(collected_at, mode, db_host, db_name) VALUES (?, ?, ?, ?)",
        (_now_iso(), "prod", cfg["host"], cfg["database"])
    )

    sqlite_conn.commit()
    sqlite_conn.close()
    cur.close()
    pg.close()

    print(f"Success: Collected {len(tables_data)} main tables and {len(chunks_data)} chunks.")

def collect_metadata():
    # 더미 모드 제거됨 - 무조건 프로덕션 수집 실행
    collect_prod_data()

if __name__ == "__main__":
    collect_metadata()