# OpenBankAPI (spec §7, §8).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/openbankapi/requirements.txt
RUN pip install --no-cache-dir -r /app/openbankapi/requirements.txt

COPY . /app/openbankapi

EXPOSE 8000
CMD ["uvicorn", "openbankapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
