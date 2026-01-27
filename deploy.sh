#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# CI Detection
IS_CI="${CI:-false}"

# Install dependencies (skip in CI, workflow handles it)
if [ "$IS_CI" != "true" ]; then
    echo "Local mode: Installing dependencies..."
    pip install psycopg2-binary python-dotenv jinja2
fi

# 1. Ensure we're on main branch
git checkout main

# 2. Fetch gh-pages and extract existing SQLite file
git fetch origin gh-pages 2>/dev/null || true
if git show origin/gh-pages:db_monitoring.sqlite > /dev/null 2>&1; then
    echo "Preserving existing database history..."
    git show origin/gh-pages:db_monitoring.sqlite > src/db_monitoring.sqlite
fi

# 3. Collect new data (appends to existing SQLite)
python src/collect_metadata.py

# 4. Generate HTML
python src/generate_static_html.py

# 5. Switch to gh-pages branch
if git show-ref --verify --quiet refs/heads/gh-pages; then
    git checkout gh-pages
    git pull origin gh-pages --no-rebase 2>/dev/null || true
else
    git checkout --orphan gh-pages
fi

# 7. Copy updated files from main
git checkout main -- index.html README.md .gitignore
cp src/db_monitoring.sqlite db_monitoring.sqlite

# 8. Add updated files
git add -f index.html README.md .gitignore db_monitoring.sqlite

# 9. Commit
git commit -m "Deploy static dashboard $(date)" || echo "No changes to commit"

# 10. Push (without --force to preserve history)
git push origin gh-pages

# 11. Switch back to main
git checkout main