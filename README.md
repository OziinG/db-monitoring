# Database Monitoring Dashboard

PostgreSQL/TimescaleDB 용량 모니터링 로그를 보여주는 정적 대시보드입니다.

## 배포된 페이지

[GitHub Pages](https://oziing.github.io/db-monitoring/)

## 로컬 개발

```bash
# 데이터 수집 및 HTML 생성
cd src
python collect_metadata.py
python generate_static_html.py

# 배포
./deploy.sh
```

## 기능

- DB 테이블 및 행 수 모니터링
- 정적 HTML로 용량 현황 표시
- GitHub Pages 자동 배포

### 로컬 개발 DB 모니터링

```bash
# 메타데이터 수집
python3 collect_local.py

# 모니터링 서버 시작 (http://localhost:8001)
python3 serve_local.py
```

### 운영 DB 모니터링

```bash
# 메타데이터 수집
python3 collect_metadata.py

# 빠른 수집 모드 (COUNT 대신 통계 사용)
python3 collect_metadata.py --fast

# 모니터링 서버 시작 (http://localhost:8000)
python3 api_server.py
```

### Docker 사용

```bash
# 컨테이너 시작
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 컨테이너 중지
docker-compose down
```

### 관리 CLI

```bash
# 환경 파일 초기화
python3 manage.py init

# 메타데이터 수집
python3 manage.py collect

# API 서버 시작
python3 manage.py serve

# Docker 실행
python3 manage.py docker-run

# 상태 확인
python3 manage.py status
```

## API 엔드포인트

### 헬스 체크
```
GET /health
```

### 테이블 목록
```
GET /api/tables?search=keyword&schema=public&sort_by=total_size_bytes&order=desc
```

### 테이블 상세 정보
```
GET /api/tables/{schema}/{table}
```

### 테이블 히스토리
```
GET /api/tables/{schema}/{table}/history?days=7
```

### 통계 요약
```
GET /api/stats/summary
```

### 스키마 목록
```
GET /api/schemas
```

### 수집 로그
```
GET /api/logs?limit=100
```

### 수집 트리거
```
POST /api/collect
```

## 설정

### .env (운영 DB)

```ini
PROD_DB_HOST=52.79.139.14
PROD_DB_PORT=5432
PROD_DB_NAME=postgres
PROD_DB_USER=postgres
PROD_DB_PASSWORD=p@ssw0rd
LOCAL_DB_PATH=db_monitoring.sqlite
API_HOST=127.0.0.1
API_PORT=8000
```

### .env.local (로컬 DB)

```ini
LOCAL_DB_HOST=localhost
LOCAL_DB_PORT=5433
LOCAL_DB_NAME=evdash
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=postgres
LOCAL_DB_PATH=db_monitoring_local.sqlite
API_HOST=127.0.0.1
API_PORT=8001
```

## 디렉토리 구조

```
db-monitoring/
├── api_server.py          # FastAPI 서버
├── collect_metadata.py    # 메타데이터 수집
├── collect_local.py       # 로컬 DB 수집
├── serve_local.py         # 로컬 모니터링 서버
├── schema.sql             # SQLite 스키마
├── requirements.txt       # Python 의존성
├── docker-compose.yml     # Docker 설정
├── Dockerfile             # 컨테이너 이미지
├── docker-entrypoint.sh   # 초기화 스크립트
├── manage.py              # 관리 CLI
├── .env                   # 운영 설정
├── .env.local             # 로컬 설정
├── static/
│   └── index.html         # 웹 대시보드
├── data/                  # SQLite 데이터
└── logs/                  # 로그 파일
```

## 주의사항

1. **운영 DB 접속**: 52.79.139.14:5432 접속 가능해야 함
2. **로컬 DB**: Docker 컨테이너가 실행 중이어야 함 (localhost:5433)
3. **포트**: 8000 (운영), 8001 (로컬) 포트가 사용 가능해야 함
4. **fast 모드**: COUNT(*) 대신 통계 사용하여 빠르지만 근사치

## 통합

local_dev_setup 모듈과 통합되어 있습니다:

```bash
# local_dev_setup에서 사용
python -m local_dev_setup.cli monitor
python -m local_dev_setup.cli monitor --collect
python -m local_dev_setup.cli monitor --serve
```

## 라이선스

EV Dashboard 프로젝트의 일부입니다.
