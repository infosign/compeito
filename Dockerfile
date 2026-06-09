FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project

COPY . .
RUN uv sync --frozen 2>/dev/null || uv sync

# Build the Tailwind stylesheet so the Web UI needs no external CDN at runtime.
# Uses the standalone Tailwind binary (no Node toolchain). The output is
# generated here (not committed); base.html serves it when present, else falls
# back to the Play CDN for zero-setup native dev.
ARG TAILWIND_VERSION=v3.4.17
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && ARCH="$(dpkg --print-architecture)" \
    && case "$ARCH" in amd64) TARCH=x64 ;; arm64) TARCH=arm64 ;; *) echo "unsupported arch: $ARCH" && exit 1 ;; esac \
    && curl -fsSL -o /usr/local/bin/tailwindcss \
       "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${TARCH}" \
    && chmod +x /usr/local/bin/tailwindcss \
    && tailwindcss -i tailwind/input.css -o src/static/css/app.css --minify \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
