# syntax=docker/dockerfile-upstream:master@sha256:655d8ec53fd4a740c5e5a7031454a72020caf93841bad4a9f7f4f4d85929c083

FROM trufflesecurity/trufflehog:3.97.4@sha256:562bc231afa9de3d04de44cfe624252b08207de1fc3cebc5e7ed92bed7f279e4 AS tool

FROM tool AS scan
WORKDIR /repo
COPY .git .git
RUN /usr/bin/trufflehog git file:///repo \
    --results=verified,unknown \
    --no-update \
    --json \
    > /tmp/trufflehog-git.json

FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40 AS gate
RUN apk add --no-cache nodejs=24.18.1-r0
WORKDIR /gate
COPY scripts/check-trufflehog-findings.mjs scripts/trufflehog-allowlist.json ./
COPY --from=scan /tmp/trufflehog-git.json ./trufflehog-git.json
RUN node check-trufflehog-findings.mjs trufflehog-git.json trufflehog-allowlist.json

FROM scratch AS evidence
COPY --from=gate /gate/trufflehog-git.json /trufflehog-git.json
