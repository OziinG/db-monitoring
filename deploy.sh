#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Install dependencies if needed
pip install psycopg2-binary python-dotenv jinja2

# 1. Collect data
python src/collect_metadata.py

# 2. Generate HTML
python src/generate_static_html.py

# 3. Switch to gh-pages branch
git checkout -B gh-pages

# 4. Add only deployable files (sqlite에 로그 이력 저장, -f로 gitignore 우회)
git add -f index.html README.md .gitignore db_monitoring.sqlite

# 5. Commit
git commit -m "Deploy static dashboard $(date)"

# 6. Push
git push origin gh-pages --force

# 7. Switch back
git checkout main