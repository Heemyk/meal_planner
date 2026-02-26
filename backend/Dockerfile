# Use bookworm (Debian 12): --with-deps works there. Trixie (slim) has font pkgs removed.
FROM python:3.11-bookworm

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN python -m playwright install --with-deps chromium

COPY app /app/app

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
