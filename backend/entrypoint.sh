#!/bin/sh
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ "${SEED_DEMO_DATA_ON_START:-false}" = "true" ]; then
  python manage.py seed_demo_data
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${GUNICORN_WORKERS:-4} --timeout ${GUNICORN_TIMEOUT:-120}
