#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Install dependencies if needed
pip install psycopg2-binary python-dotenv jinja2

# 1. Fetch and checkout gh-pages to get existing SQLite file
git fetch origin gh-pages 2>/dev/null || true
git checkout gh-pages 2>/dev/null || git checkout --orphan gh-pages

# 2. Pull latest to preserve history
git pull origin gh-pages --no-rebase 2>/dev/null || true

# 3. Copy existing SQLite to src/ (preserve historical data)
if [ -f "db_monitoring.sqlite" ]; then
    echo "Preserving existing database history..."
    cp db_monitoring.sqlite src/db_monitoring.sqlite
fi

# 4. Collect new data (appends to existing SQLite)
python src/collect_metadata.py

# 5. Generate HTML
python src/generate_static_html.py

# 6. Copy updated SQLite back to root
cp src/db_monitoring.sqlite db_monitoring.sqlite

# 7. Add updated files
git add -f index.html README.md .gitignore db_monitoring.sqlite

# 8. Commit
git commit -m "Deploy static dashboard $(date)" || echo "No changes to commit"

# 9. Push (without --force to preserve history)
git push origin gh-pages

# 10. Switch back to main
git checkout main