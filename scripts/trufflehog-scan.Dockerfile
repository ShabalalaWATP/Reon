# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM trufflesecurity/trufflehog:3.96.0@sha256:aa821cf4ace8861c7d096d83818cdf7bb9719028a52d37a52eaad44086a52577 AS tool

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
