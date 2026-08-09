# syntax=docker/dockerfile:1.7

FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /workspace
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --filter @istari-service/web... --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --filter @istari-service/web build

FROM nginx:1.31.3-alpine@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
# Validate syntax without requiring the Compose-only API hostname at image-build time.
RUN sed -i '/^user[[:space:]]/d; s#pid[[:space:]]\+/var/run/nginx.pid;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && sed -i 's#pid[[:space:]]\+/run/nginx.pid;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && grep -qx 'pid /tmp/nginx.pid;' /etc/nginx/nginx.conf \
    && sed -i 's#/var/cache/nginx/#/tmp/nginx/#g' /etc/nginx/nginx.conf \
    && mkdir -p /tmp/nginx/client_temp /tmp/nginx/proxy_temp \
        /tmp/nginx/fastcgi_temp /tmp/nginx/uwsgi_temp /tmp/nginx/scgi_temp \
    && chown -R 101:101 /tmp/nginx \
    && cp /etc/nginx/conf.d/default.conf /tmp/default.conf \
    && sed -i 's/http:\/\/api:8000/http:\/\/127.0.0.1:8000/' /etc/nginx/conf.d/default.conf \
    && nginx -t \
    && mv /tmp/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /workspace/apps/web/dist /usr/share/nginx/html

USER 101:101

EXPOSE 8080
