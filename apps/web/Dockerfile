# syntax=docker/dockerfile-upstream:master@sha256:655d8ec53fd4a740c5e5a7031454a72020caf93841bad4a9f7f4f4d85929c083

FROM node:24-alpine@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43 AS build
WORKDIR /workspace
# Install the package manager directly because newer Node.js images do not
# consistently bundle Corepack and may retain conflicting legacy shims.
RUN npm install --global pnpm@11.21.0 \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
        /opt/yarn-v1.22.22 \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
        /usr/local/bin/yarn /usr/local/bin/yarnpkg
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
    && mkdir -p /tmp/nginx-client-temp /tmp/nginx-proxy-temp \
        /tmp/nginx/fastcgi_temp /tmp/nginx/uwsgi_temp /tmp/nginx/scgi_temp \
    && chown -R 101:101 /tmp/nginx /tmp/nginx-client-temp /tmp/nginx-proxy-temp \
    && cp /etc/nginx/conf.d/default.conf /tmp/default.conf \
    && sed -i 's/http:\/\/api:8000/http:\/\/127.0.0.1:8000/' /etc/nginx/conf.d/default.conf \
    && nginx -t \
    && mv /tmp/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /workspace/apps/web/dist /usr/share/nginx/html

USER 101:101

EXPOSE 8080
