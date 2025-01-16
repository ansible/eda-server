# Build eda-ui
FROM mirror.gcr.io/node:18-alpine AS ui-builder

WORKDIR /app/ansible-ui

COPY tmp/ansible-ui/package-*.json /app/ansible-ui/
RUN npm ci --omit=dev --omit=optional --ignore-scripts

COPY tmp/ansible-ui /app/ansible-ui
RUN cd /app/ansible-ui && npm run build:eda

FROM mirror.gcr.io/nginx
ARG NGINX_CONF=tools/docker/nginx/default.conf
ARG NGINX_CONFIGURATION_PATH=/etc/nginx/conf.d/

ENV DIST_UI="/opt/app-root/ui/eda"

ADD ${NGINX_CONF} ${NGINX_CONFIGURATION_PATH}

# Set up permissions
ARG USER_ID=${USER_ID:-1001}
RUN useradd --uid "$USER_ID" --gid 0 --home-dir /app --create-home eda

# Pre-create things we need to access
USER 0

RUN for dir in \
      ${DIST_UI}/ \
      ${NGINX_CONF} \
      ${NGINX_CONFIGURATION_PATH} \
      /var/cache/nginx \
      /var/log/nginx \
      /var/lib/nginx ; \
    do mkdir -m 0775 -p $dir ; chmod g+rwx $dir ; chgrp root $dir ; done && \
    for file in \
      /var/run/nginx.pid ; \
    do touch $file ; chmod g+rw $file ; done

# Copy dist dir to final location
RUN mkdir -p ${DIST_UI}/
COPY --from=ui-builder /app/ansible-ui/build/eda/ ${DIST_UI}

USER "$USER_ID"
