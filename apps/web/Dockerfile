# syntax=docker/dockerfile:1.7

FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /workspace
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --filter @istari-service/web... --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --filter @istari-service/web build

FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de
RUN apk upgrade --no-cache
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
# Validate syntax without requiring the Compose-only API hostname at image-build time.
RUN cp /etc/nginx/conf.d/default.conf /tmp/default.conf \
    && sed -i 's/http:\/\/api:8000/http:\/\/127.0.0.1:8000/' /etc/nginx/conf.d/default.conf \
    && nginx -t \
    && mv /tmp/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html
EXPOSE 80
