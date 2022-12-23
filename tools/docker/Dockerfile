FROM registry.access.redhat.com/ubi9/ubi
ARG USER_ID=${USER_ID:-1001}

RUN useradd --system --uid "$USER_ID" --gid 0 --home-dir /app --create-home eda

RUN DNF=dnf \
    INSTALL_PACKAGES="python3 python3-devel python3-pip libpq-devel gcc" \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

USER "$USER_ID"
ENV POETRY_VERSION='1.3.1' \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/app/venv \
    PATH="/app/venv/bin:/app/.local/bin:$PATH" \
    DJANGO_SETTINGS_MODULE="aap_eda.settings.development"

RUN python3 -m pip install --user "poetry==${POETRY_VERSION}" \
    && python3 -m venv "$VIRTUAL_ENV" \
    && poetry config virtualenvs.create false

WORKDIR /app/src

COPY pyproject.toml poetry.lock /app/src/
RUN poetry install --no-interaction --no-ansi --no-root
COPY . /app/src
RUN poetry install --only-root

CMD ["django-admin", "runserver", "0.0.0.0:8000"]
