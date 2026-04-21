#!/bin/sh

# Veritabanı migration scriptlerini çalıştır (varsa)
if ls migration_*.py >/dev/null 2>&1; then
    echo "Running migration scripts..."
    for f in migration_*.py; do
        echo "Running ${f}..."
        python "$f"
    done
fi

# Uygulamayı başlat
echo "Starting Gunicorn..."
exec gunicorn -k eventlet -b 0.0.0.0:5000 --workers 1 --timeout 120 app:app
