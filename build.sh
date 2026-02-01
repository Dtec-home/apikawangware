#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Sync YouTube videos (if API key is configured)
echo "Syncing YouTube videos..."
python manage.py sync_youtube_videos --channel --max-results 50 || echo "YouTube sync skipped (API key not configured or failed)"

# Create superuser if it doesn't exist
python manage.py create_superuser

# Seed default contribution categories
python manage.py create_default_categories
