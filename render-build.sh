#!/usr/bin/env bash

set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

if [[ -n "$DJANGO_SUPERUSER_USERNAME" || -n "$DJANGO_SUPERUSER_EMAIL" || -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
  python manage.py ensure_superuser
else
  echo "Skipping superuser setup; DJANGO_SUPERUSER_* env vars are not all set."
fi
