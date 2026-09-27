#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
cd frontend
bun install
bun run build
cd ..
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py bootstrap_demo

if [ "${SMARTQ_LIVE_STUDY_ENABLED:-false}" = "true" ]; then
  python manage.py run_pretoria_live_study \
    --date "${SMARTQ_LIVE_STUDY_DATE}" \
    --start-time "${SMARTQ_LIVE_STUDY_START:-02:00}" \
    --customers "${SMARTQ_LIVE_STUDY_CUSTOMERS:-15}" \
    --priority "${SMARTQ_LIVE_STUDY_PRIORITY:-5}" \
    --window-minutes "${SMARTQ_LIVE_STUDY_WINDOW_MINUTES:-90}" \
    --branch-code PTA01 \
    --prepare-only
fi
