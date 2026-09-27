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
