# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

# v8.30.1 has a confirmed default-rule regression. Keep the last reviewed
# release pinned until that upstream issue is resolved and a control token test
# passes for the replacement.
FROM zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f AS upstream

FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40 AS tool
COPY --from=upstream /usr/bin/gitleaks /usr/local/bin/gitleaks
ENTRYPOINT ["gitleaks"]

FROM tool AS scan
WORKDIR /source
COPY . .
RUN gitleaks dir /source \
    --redact \
    --no-banner \
    --exit-code 1 \
    --report-format json \
    --report-path /tmp/gitleaks-source.json

FROM scratch AS evidence
COPY --from=scan /tmp/gitleaks-source.json /gitleaks-source.json
