# Dockerfile para projeto Django
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia tudo do backend (um nível acima do monitor)
COPY .. .

ENV PYTHONUNBUFFERED=1

WORKDIR /app/monitor

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
