FROM quay.io/centos/centos:stream9

ARG USER_ID=${USER_ID:-1001}
ARG STATIC_ROOT=/var/lib/eda/static

# python3.12 supported
ARG PYTHON_BIN="python3.12"
ARG ANSIBLE_CORE_VER=2.16

RUN useradd --uid "$USER_ID" --gid 0 --home-dir /app --create-home eda \
    && mkdir -p /app/.local /var/lib/eda/ \
    && chown -R "${USER_ID}:0" /app/.local /var/lib/eda \
    && chmod 0775 /app /var/lib/eda

RUN mkdir -p /var/lib/eda/redis-tls \
    && chown -R "${USER_ID}:0" /var/lib/eda/redis-tls \
    && chmod 0775 /var/lib/eda/redis-tls
COPY ./tools/docker/redis-tls /var/lib/eda/redis-tls

RUN DNF=dnf \
    INSTALL_PACKAGES="${PYTHON_BIN} \
    ${PYTHON_BIN}-devel \
    ${PYTHON_BIN}-pip \
    libpq-devel \
    libffi-devel \
    git \
    openssh-clients \
    gcc \
    gettext \
    git-core \
    tzdata \
    java-17-openjdk-headless" \
    && $DNF -y install dnf-plugins-core \
    && $DNF -y config-manager --set-enabled crb \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

USER "$USER_ID"
ENV POETRY_VERSION="2.*" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    VIRTUAL_ENV=/app/venv \
    SOURCES_DIR=/app/src \
    PATH="/app/.local/bin:$PATH" \
    HOME="/app"

USER "$USER_ID"

# Setup SSH for non-root user
RUN mkdir -p /app/.ssh \
    && ssh-keyscan github.com >> /app/.ssh/known_hosts \
    && chmod 700 /app/.ssh \
    && chmod 644 /app/.ssh/known_hosts

# Install poetry, create virtual environment
RUN ${PYTHON_BIN} -m pip install --user "poetry==${POETRY_VERSION}" \
    && ${PYTHON_BIN} -m venv "$VIRTUAL_ENV" \
    && poetry config virtualenvs.create false \
    && poetry config system-git-client true

WORKDIR $SOURCES_DIR

ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

COPY poetry.toml pyproject.toml poetry.lock $SOURCES_DIR/

# Keep dependency files writable by the build user.
USER 0
RUN chown -R ${USER_ID}:0 "$SOURCES_DIR"

USER "$USER_ID"
RUN --mount=type=secret,id=git_ssh_key,target=/run/secrets/git_ssh_key,required=false,uid=${USER_ID},gid=0,mode=0400 \
    if [ -f /run/secrets/git_ssh_key ]; then \
        GIT_SSH_COMMAND="ssh -i /run/secrets/git_ssh_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
            poetry install -E all --no-root --no-cache; \
    else \
        poetry install -E all --no-root --no-cache; \
    fi && \
    ${PYTHON_BIN} -m pip install gunicorn
COPY . $SOURCES_DIR/
RUN poetry install -E all --only-root
RUN pip install ansible-core==${ANSIBLE_CORE_VER}
RUN EDA_SECRET_KEY=dummy EDA_STATIC_ROOT=${STATIC_ROOT} aap-eda-manage collectstatic --noinput --clear

USER 0
RUN for dir in \
    /app \
    /app/venv \
    /app/venv/bin ; \
    do mkdir -m 0775 -p $dir ; chmod g+rwx $dir ; chgrp root $dir ; done

USER "$USER_ID"

# Red Hat patches downstream RPM packages (python3-certifi,
# python3-requests, and the system Python binary) to automatically
# redirect certificate lookups to the OS trust store at
# /etc/pki/tls/certs/ca-bundle.crt. However, when applications run
# inside a virtual environment (/app/venv), pip installs vanilla,
# upstream wheels directly from PyPI. These unpatched PyPI packages
# bypass the OS entirely, relying instead on an isolated, embedded
# Mozilla certificate bundle that has no awareness of Red Hat
# system paths or your mounted enterprise CAs.

# Setting REQUESTS_CA_BUNDLE and SSL_CERT_FILE to
# /etc/pki/tls/certs/ca-bundle.crt bridges this disconnect on RHEL/CentOS.
# It forces both higher-level HTTP libraries (requests, urllib3)
# and low-level Python/OpenSSL standard library calls inside your
# virtualenv to ignore their isolated bundles and route trust
# verification back through the unified Linux host certificate store.

ENV REQUESTS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt \
    SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt
CMD ["aap-eda-manage", "runserver", "0.0.0.0:8000"]
