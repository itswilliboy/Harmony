FROM ghcr.io/astral-sh/uv:python3.12-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.6.1 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

ADD . /app
WORKDIR /app

RUN apt-get -y update
RUN apt-get -y install git

RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen

EXPOSE 8013

ENTRYPOINT [ "uv", "run", "." ]
