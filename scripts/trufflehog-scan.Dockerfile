# syntax=docker/dockerfile:1.7

FROM trufflesecurity/trufflehog:3.96.0@sha256:aa821cf4ace8861c7d096d83818cdf7bb9719028a52d37a52eaad44086a52577 AS scan
WORKDIR /repo
COPY .git .git
RUN /usr/bin/trufflehog git file:///repo \
    --results=verified,unknown \
    --no-update \
    --json \
    > /tmp/trufflehog-git.json

FROM node:25-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS gate
WORKDIR /gate
COPY scripts/check-trufflehog-findings.mjs scripts/trufflehog-allowlist.json ./
COPY --from=scan /tmp/trufflehog-git.json ./trufflehog-git.json
RUN node check-trufflehog-findings.mjs trufflehog-git.json trufflehog-allowlist.json

FROM scratch AS evidence
COPY --from=gate /gate/trufflehog-git.json /trufflehog-git.json
