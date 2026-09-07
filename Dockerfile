FROM python:3.12-slim

WORKDIR /service

COPY pyproject.toml ./
COPY alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY data ./data
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
