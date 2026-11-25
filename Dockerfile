FROM python:3.12-slim

WORKDIR /code

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY app ./app

RUN uv sync --no-dev

ENV PORT=8080
EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.agent:app", "--host", "0.0.0.0", "--port", "8080"]
