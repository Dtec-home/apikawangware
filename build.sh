#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Create default superuser if it doesn't exist
python manage.py create_superuser

# Seed default contribution categories
python manage.py create_default_categories


