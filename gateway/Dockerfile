# FastAPI API Gateway (spec §6).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/gateway/requirements.txt
RUN pip install --no-cache-dir -r /app/gateway/requirements.txt

COPY . /app/gateway

EXPOSE 8000
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
