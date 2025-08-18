#!/bin/bash
# Startup script for Google Cloud Run with Cloud SQL

set -e

echo "Starting Portfolio Analyzer on Cloud Run..."

# Initialize database if needed
if [ "$INIT_DATABASE" = "true" ]; then
    echo "Initializing database schema..."
    python -c "
try:
    from config.database import init_database
    init_database()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    # Continue anyway - database might already be initialized
"
fi

# Start the application with Gunicorn
echo "Starting Gunicorn server..."
exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${GUNICORN_WORKERS:-2} \
    --worker-class gthread \
    --threads ${GUNICORN_THREADS:-4} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --keep-alive ${GUNICORN_KEEPALIVE:-5} \
    --max-requests ${GUNICORN_MAX_REQUESTS:-1000} \
    --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-100} \
    --preload \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    app:app