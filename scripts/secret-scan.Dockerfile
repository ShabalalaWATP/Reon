# syntax=docker/dockerfile:1.7

# v8.30.1 has a confirmed default-rule regression. Keep the last reviewed
# release pinned until that upstream issue is resolved and a control token test
# passes for the replacement.
FROM zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f AS scan
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
