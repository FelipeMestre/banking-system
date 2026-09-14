# OpenBankAPI (spec §7, §8).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/openbankapi/requirements.txt
RUN pip install --no-cache-dir -r /app/openbankapi/requirements.txt

COPY . /app/openbankapi

# `batch/` is copied in above already (it lives inside this build context, at
# `openbankapi/batch/`) — `cron` is the only extra OS package the batch
# worker needs. `batch-worker` (docker-compose.yml) reuses this same image.
RUN apt-get update && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*
COPY batch/crontab /etc/cron.d/batch-worker
RUN chmod 0644 /etc/cron.d/batch-worker && crontab /etc/cron.d/batch-worker

EXPOSE 8000
CMD ["uvicorn", "openbankapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
