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

# 1. Collect new data (updates existing SQLite)
echo "Collecting database metadata..."
python src/collect_metadata.py

# 2. Generate HTML
echo "Generating static HTML..."
python src/generate_static_html.py

# 3. Commit changes (only if not in CI)
if [ "$IS_CI" != "true" ]; then
    echo "Committing changes..."
    git add src/db_monitoring.sqlite index.html
    git commit -m "Update dashboard $(date +'%Y-%m-%d %H:%M:%S')" || echo "No changes to commit"

    echo "Pushing to main..."
    git push origin main
fi

echo "✓ Deployment complete!"
