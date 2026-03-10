FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project

COPY . .
RUN uv sync --frozen 2>/dev/null || uv sync

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
