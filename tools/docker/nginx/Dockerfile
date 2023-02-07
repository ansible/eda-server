#FROM docker.io/nginx
#ARG NGINX_CONF=tools/docker/nginx/default.conf
#ARG NGINX_CONFIGURATION_PATH=/etc/nginx/conf.d/
#
#ADD ${NGINX_CONF} ${NGINX_CONFIGURATION_PATH}

# Build eda-frontend
FROM docker.io/node:16-alpine AS ui-builder

#ARG username=$GIT_USERNAME
#ARG password=$GIT_PASSWORD
#RUN git clone https://username:password@github.com:eugenp/tutorials.git

RUN apk add --no-cache git
RUN apk add --no-cache openssh

ARG SSH_PRIVATE_KEY=$SSH_PRIVATE_KEY

RUN mkdir /root/.ssh/
RUN echo "${SSH_PRIVATE_KEY}" > /root/.ssh/id_rsa
RUN git clone git@github.com:ansible/ansible-ui.git
RUN rm /root/.ssh/id_rsa

WORKDIR /ansible-ui
COPY ansible-ui/package-*.json ./
RUN npm ci --omit=dev --omit=optional --ignore-scripts
COPY ansible-ui/. .
RUN npm run build:eda

#---------------------------
FROM docker.io/nginx
ARG NGINX_CONF=tools/docker/nginx/default.conf
ARG NGINX_CONFIGURATION_PATH=/etc/nginx/conf.d/

ENV DIST_UI="/opt/app-root/ui/eda"

ADD ${NGINX_CONF} ${NGINX_CONFIGURATION_PATH}

# Copy dist dir to final location
RUN mkdir -p ${DIST_UI}/
COPY --from=ui-builder /ansible-ui/build/eda/ ${DIST_UI}