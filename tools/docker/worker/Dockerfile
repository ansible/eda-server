FROM registry.access.redhat.com/ubi9/ubi
ARG USER_ID=${USER_ID:-1001}

RUN useradd --uid "$USER_ID" --gid 0 --home-dir /app --create-home eda \
    && mkdir -p /var/lib/eda/ \
    && chown "${USER_ID}:0" /var/lib/eda \
    && chmod g+w /var/lib/eda

RUN DNF=dnf \
    INSTALL_PACKAGES="python3 python3-devel python3-pip libpq-devel gcc git-core" \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

RUN dnf install -y java-17-openjdk-devel
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk

RUN pip install -U pip \
    && pip install ansible \
    ansible-runner \
    ansible-rulebook \
    jmespath \
    asyncio \
    aiohttp \
    aiokafka \
    watchdog \
    azure-servicebus \
    && ansible-galaxy collection install ansible.eda

RUN ansible-galaxy collection install git+https://github.com/ansible/event-driven-ansible.git --force

USER "$USER_ID"
ENV POETRY_VERSION='1.4.0' \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    VIRTUAL_ENV=/app/venv \
    SOURCES_DIR=/app/src \
    PATH="/app/venv/bin:/app/.local/bin:$PATH"

RUN python3 -m pip install --user "poetry==${POETRY_VERSION}" \
    && python3 -m venv "$VIRTUAL_ENV" \
    && poetry config virtualenvs.create false

WORKDIR $SOURCES_DIR

COPY pyproject.toml poetry.lock $SOURCES_DIR/
RUN poetry install -E all --no-root
COPY . $SOURCES_DIR/
RUN poetry install -E all --only-root

CMD ["aap-eda-manage", "runserver", "0.0.0.0:8000"]
