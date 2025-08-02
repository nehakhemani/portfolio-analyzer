 
 FROM python:3.10-slim

  WORKDIR /app

  ENV PYTHONDONTWRITEBYTECODE=1
  ENV PYTHONUNBUFFERED=1
  ENV PORT=8080
  
  RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
  
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .
  RUN mkdir -p uploads backend/data

  EXPOSE $PORT

  # Use main.py as entry point
  CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:applicationn --bind :$PORT --workers 1 --threads 8 --timeout 0 --pythonpath /app/backend
backend.app:app