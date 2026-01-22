#!/bin/bash
set -e

# Install dependencies if needed
pip install psycopg2-binary python-dotenv jinja2

# 1. Collect data
cd src
python collect_metadata.py
cd ..

# 2. Generate HTML
cd src
python generate_static_html.py
cd ..

# 3. Switch to gh-pages branch
git checkout -B gh-pages

# 4. Add only deployable files
git add index.html README.md .gitignore

# 5. Commit
git commit -m "Deploy static dashboard $(date)"

# 6. Push
git push origin gh-pages --force

# 7. Switch back
git checkout main