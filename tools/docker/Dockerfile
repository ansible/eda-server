FROM registry.access.redhat.com/ubi9/ubi:latest

ARG USER_ID=${USER_ID:-1001}
RUN useradd --uid "$USER_ID" --gid 0 --home-dir /app --create-home eda \
    && mkdir -p /app/.local /var/lib/eda/ \
    && chown -R "${USER_ID}:0" /app/.local /var/lib/eda \
    && chmod 0775 /app /var/lib/eda

RUN DNF=dnf \
    INSTALL_PACKAGES="python3 \
    python3-devel \
    python3-pip \
    libpq-devel \
    gcc \
    gettext \
    git-core \
    java-17-openjdk-headless \
    # LDAP Integration for 2.4 https://issues.redhat.com/browse/AAP-16938
    openldap-devel" \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

USER "$USER_ID"
ENV POETRY_VERSION='1.4.0' \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    VIRTUAL_ENV=/app/venv \
    SOURCES_DIR=/app/src \
    PATH="/app/.local/bin:$PATH"

# Install poetry, create virtual environment
RUN python3 -m pip install --user "poetry==${POETRY_VERSION}" \
    && python3 -m venv "$VIRTUAL_ENV" \
    && poetry config virtualenvs.create false

WORKDIR $SOURCES_DIR

ENV PATH="${VIRTUAL_ENV}/bin:$PATH"
COPY pyproject.toml poetry.lock $SOURCES_DIR/
RUN poetry install -E all --no-root --no-cache \
    && python3 -m pip install gunicorn
COPY . $SOURCES_DIR/
RUN poetry install -E all --only-root

USER 0
RUN for dir in \
      /app \
      /app/venv \
      /app/venv/bin ; \
    do mkdir -m 0775 -p $dir ; chmod g+rwx $dir ; chgrp root $dir ; done

USER "$USER_ID"

CMD ["aap-eda-manage", "runserver", "0.0.0.0:8000"]
