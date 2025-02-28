ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5.5

FROM ghcr.io/astral-sh/uv:${UV_VERSION}-python${PYTHON_VERSION}-bookworm

ARG FFMPEG_VERSION=7:5.1.6-0+deb12u1

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_SYSTEM_PYTHON=1

WORKDIR /src

# Install system dependencies
RUN apt-get update && \
  apt-get install -y build-essential ffmpeg=${FFMPEG_VERSION} && \
  rm -rf /var/lib/apt/lists/*

RUN useradd -m appuser && chown -R appuser:appuser /src
USER appuser

COPY pyproject.toml uv.lock supervisord.conf ./

RUN uv sync --no-dev --frozen --no-install-project

COPY ./app/ ./app/

RUN uv sync --no-dev --frozen --no-editable

EXPOSE ${PORT}

CMD ["uv", "run", "--no-dev", "--no-sync",  "supervisord", "-c", "supervisord.conf"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl --fail http://localhost:${PORT}/health || exit 1
