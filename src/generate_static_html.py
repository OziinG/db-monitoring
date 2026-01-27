"""Generate static HTML dashboard from DB monitoring logs."""

import sqlite3
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# 스크립트 위치 기준 경로 설정
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
LOCAL_DB_PATH = SCRIPT_DIR / "db_monitoring.sqlite"

def bytes_to_gb(bytes_val):
    """Convert bytes to GB with 2 decimal places."""
    if not bytes_val:
        return 0.0
    return round(bytes_val / (1024 ** 3), 2)

def collect_data():
    """Collect data from SQLite for static HTML."""
    if not Path(LOCAL_DB_PATH).exists():
        return {"tables": [], "stats": {"total_tables": 0, "total_rows": 0}, "logs": {}}

    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()

    # Get tables (size in GB)
    # [수정됨] collect_metadata.py가 이미 청크를 제외한 'tables'만 저장하므로
    # 별도의 필터링이나 합산 로직 없이 그대로 가져옵니다.
    cursor.execute("SELECT name, schema_name, table_type, actual_rows, is_compressed, table_size FROM tables ORDER BY schema_name, name")
    tables = [
        {
            "name": row[0],
            "schema": row[1],
            "type": row[2],
            "rows": row[3],
            "compressed": row[4],
            "size": bytes_to_gb(row[5])  # bytes → GB
        }
        for row in cursor.fetchall()
    ]

    # [삭제됨] 여기에 있던 _all_chunks 합산 로직(chunk_tables, aggregated 등)을 모두 제거했습니다.

    # Get stats
    # tables 리스트에 중복(청크)이 없으므로 단순 합계가 곧 전체 용량입니다.
    stats = {
        "total_tables": len(tables),
        "total_rows": sum(int(t.get("rows") or 0) for t in tables),
        "total_size": sum(float(t.get("size") or 0) for t in tables),
    }

    # Get logs for each table
    logs = {}
    for table in tables:
        key = f"{table['schema']}.{table['name']}"
        cursor.execute("""
            SELECT date, row_count, table_size FROM table_logs
            WHERE table_name = ? AND schema_name = ?
            ORDER BY date
        """, (table['name'], table['schema']))
        logs[key] = [{"date": row[0], "rows": row[1], "size": bytes_to_gb(row[2])} for row in cursor.fetchall()]

    conn.close()
    return {"tables": tables, "stats": stats, "logs": logs}

def inject_sorting_js(html: str) -> str:
    """Inject sortable table JS without changing template/design."""
    js = """
<script>
(function () {
  function getCellValue(tr, idx) {
    return tr.children[idx].innerText.trim();
  }

  function comparer(idx, asc) {
    return function (a, b) {
      const v1 = getCellValue(asc ? a : b, idx);
      const v2 = getCellValue(asc ? b : a, idx);

      const n1 = parseFloat(v1.replace(/[^0-9.-]/g, ''));
      const n2 = parseFloat(v2.replace(/[^0-9.-]/g, ''));

      if (!isNaN(n1) && !isNaN(n2)) return n1 - n2;
      return v1.localeCompare(v2, undefined, {numeric: true, sensitivity: 'base'});
    };
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('table thead th').forEach(function (th, idx) {
      let asc = true;
      th.style.cursor = 'pointer';
      th.addEventListener('click', function () {
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        Array.from(tbody.querySelectorAll('tr'))
          .sort(comparer(idx, asc = !asc))
          .forEach(tr => tbody.appendChild(tr));
      });
    });
  });
})();
</script>
"""
    return html.replace("</body>", js + "\n</body>")


def generate_html():
    data = collect_data()
    env = Environment(loader=FileSystemLoader(SCRIPT_DIR / 'templates'))
    template = env.get_template('index.html.jinja')
    html = template.render(data=data)
    html = inject_sorting_js(html)

    with open(PROJECT_DIR / 'index.html', 'w') as f:
        f.write(html)

    print("Static HTML generated at index.html")


if __name__ == "__main__":
    generate_html()