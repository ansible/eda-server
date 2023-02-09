# Build eda-ui
FROM docker.io/node:16-alpine AS ui-builder

WORKDIR /app/ansible-ui

COPY tmp/ansible-ui/package-*.json /app/ansible-ui/
RUN npm ci --omit=dev --omit=optional --ignore-scripts

COPY tmp/ansible-ui /app/ansible-ui
RUN cd /app/ansible-ui && npm run build:eda

FROM docker.io/nginx
ARG NGINX_CONF=tools/docker/nginx/default.conf
ARG NGINX_CONFIGURATION_PATH=/etc/nginx/conf.d/

ENV DIST_UI="/opt/app-root/ui/eda"

ADD ${NGINX_CONF} ${NGINX_CONFIGURATION_PATH}

# Copy dist dir to final location
RUN mkdir -p ${DIST_UI}/
COPY --from=ui-builder /app/ansible-ui/build/eda/ ${DIST_UI}
