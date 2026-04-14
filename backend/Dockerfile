FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000

CMD ["./scripts/start-dev.sh"]
