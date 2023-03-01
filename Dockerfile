FROM registry.access.redhat.com/ubi9/ubi-minimal:latest AS base

ENV VIRTUAL_ENV='/venv' \
    PATH="/venv/bin:$PATH"

RUN set -ex; DNF=microdnf \
    INSTALL_PACKAGES="python3 git-core libpq" \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

# Stage: Build
# -------------------------------------
FROM base AS build

ENV POETRY_VERSION='1.3.2' \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    SOURCES_DIR=/src \
    PATH="$PATH:/root/.local/bin"

RUN set -ex; DNF=microdnf \
    INSTALL_PACKAGES="python3-pip python3-devel libpq-devel gcc" \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

RUN python3 -m pip install --user "poetry==${POETRY_VERSION}" \
    && python3 -m venv "${VIRTUAL_ENV}" \
    && poetry config virtualenvs.create false

WORKDIR $SOURCES_DIR
COPY pyproject.toml poetry.lock $SOURCES_DIR/

RUN python -m pip install -U pip \
    && poetry install --no-interaction --no-ansi --no-root \
        --only=main --extras=all

COPY . $SOURCES_DIR

RUN poetry build --format wheel \
    && pip install --no-deps dist/*.whl


# Stage: Final
# -------------------------------------
FROM base
ARG USER_ID="${USER_ID:-1001}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --uid "$USER_ID" --gid 0 --home-dir /var/lib/eda --create-home eda \
    && mkdir -p /var/lib/eda/files \
    && chown -R "${USER_ID}:0" /var/lib/eda \
    && chmod -R g+w /var/lib/eda

COPY --from=build /venv /venv

USER "$USER_ID"

# TODO(cutwater): Implement custom entrypoint to run server or worker without
#                 additional configuration
