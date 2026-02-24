#!/bin/sh

# O shell irá encerrar a execução do script quando um comando falhar
set -e

# while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
#   echo "🟡 Waiting for Postgres Database Startup ($POSTGRES_HOST $POSTGRES_PORT) ..."
#   sleep 2
# done

# echo "✅ Postgres Database Started Successfully ($POSTGRES_HOST:$POSTGRES_PORT)"

python manage.py collectstatic --noinput
python manage.py makemigrations --noinput
python manage.py migrate --noinput
sleep 0.2

#python manage.py runserver 0.0.0.0:8000
gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --access-logfile - \
    --error-logfile - \
    --log-level info