FROM registry.access.redhat.com/ubi9/ubi
ARG USER_ID=${USER_ID:-1001}

RUN useradd --uid "$USER_ID" --gid 0 --home-dir /app --create-home eda

RUN DNF=dnf \
    INSTALL_PACKAGES="python3 python3-devel python3-pip libpq-devel gcc git" \
    && $DNF -y install $INSTALL_PACKAGES \
    && $DNF -y clean all \
    && rm -rf /var/cache/dnf

USER "$USER_ID"
ENV POETRY_VERSION='1.3.1' \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    VIRTUAL_ENV=/app/venv \
    PATH="/app/venv/bin:/app/.local/bin:$PATH"

RUN python3 -m pip install --user "poetry==${POETRY_VERSION}" \
    && python3 -m venv "$VIRTUAL_ENV" \
    && poetry config virtualenvs.create false

WORKDIR /app/src

COPY pyproject.toml poetry.lock ${WORKDIR}
RUN poetry install -E all --no-root
COPY . ${WORKDIR}
RUN poetry install -E all --only-root


# Pre-create things we need to access
USER 0
RUN for dir in \
      /app \
      /app/venv \
      /app/venv/bin ; \
    do mkdir -m 0775 -p $dir ; chmod g+rwx $dir ; chgrp root $dir ; done && \
    for file in \
      /etc/subuid \
      /etc/subgid \
      /etc/group \
      /etc/passwd ; \
    do touch $file ; chmod g+rw $file ; chgrp root $file ; done

USER "$USER_ID"


CMD ["aap-eda-manage", "runserver", "0.0.0.0:8000"]
