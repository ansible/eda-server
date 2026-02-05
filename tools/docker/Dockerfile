FROM quay.io/centos/centos:stream9

ARG USER_ID=${USER_ID:-1001}
ARG STATIC_ROOT=/var/lib/eda/static

# python3.11 and python3.12 supported
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

# Setup SSH for non-root user
RUN mkdir -p /app/.ssh && touch /app/.ssh/known_hosts && \
    ssh-keyscan github.com >> /app/.ssh/known_hosts

# Install poetry, create virtual environment
RUN ${PYTHON_BIN} -m pip install --user "poetry==${POETRY_VERSION}" \
    && ${PYTHON_BIN} -m venv "$VIRTUAL_ENV" \
    && poetry config virtualenvs.create false \
    && poetry config system-git-client true

WORKDIR $SOURCES_DIR

ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

COPY poetry.toml pyproject.toml poetry.lock $SOURCES_DIR/

# Use SSH key to access private git repositories (if provided)
USER 0
RUN --mount=type=secret,id=git_ssh_key,target=/tmp/git_ssh_key,required=false \
    mkdir -p /app/.ssh && \
    if [ -f /tmp/git_ssh_key ]; then \
        cp /tmp/git_ssh_key /app/.ssh/github_key && \
        chmod 600 /app/.ssh/github_key && \
        chown ${USER_ID}:0 /app/.ssh/github_key; \
    fi && \
    chown -R ${USER_ID}:0 $SOURCES_DIR

USER "$USER_ID"
RUN if [ -f /app/.ssh/github_key ]; then \
        export GIT_SSH_COMMAND="ssh -i /app/.ssh/github_key -o StrictHostKeyChecking=accept-new" && \
        echo "Testing SSH connection to GitHub..." && \
        ssh -i /app/.ssh/github_key -o StrictHostKeyChecking=accept-new -T git@github.com || echo "SSH test completed (exit code expected)" && \
        poetry install -E all --no-root --no-cache && \
        ${PYTHON_BIN} -m pip install gunicorn && \
        rm -f /app/.ssh/github_key; \
    else \
        poetry install -E all --no-root --no-cache && \
        ${PYTHON_BIN} -m pip install gunicorn; \
    fi
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

CMD ["aap-eda-manage", "runserver", "0.0.0.0:8000"]
