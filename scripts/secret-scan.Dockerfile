# syntax=docker/dockerfile:1.7

# v8.30.1 has a confirmed default-rule regression. Keep the last reviewed
# release pinned until that upstream issue is resolved and a control token test
# passes for the replacement.
FROM zricethezav/gitleaks:v8.30.0@sha256:691af3c7c5a48b16f187ce3446d5f194838f91238f27270ed36eef6359a574d9 AS scan
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
