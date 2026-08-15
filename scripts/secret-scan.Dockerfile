# syntax=docker/dockerfile-upstream:master@sha256:655d8ec53fd4a740c5e5a7031454a72020caf93841bad4a9f7f4f4d85929c083

# Keep the reviewed v8.30.1 rules and CLI while rebuilding its static binary
# with patched Go and x/* modules.
FROM golang:1.26.5-alpine3.23@sha256:622e56dbc11a8cfe87cafa2331e9a201877271cbff918af53d3be315f3da88cc AS build
WORKDIR /build
RUN go mod init mist.local/gitleaks-build \
    && go get github.com/zricethezav/gitleaks/v8@v8.30.1 \
    && go get golang.org/x/crypto@v0.52.0 golang.org/x/text@v0.39.0 \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" \
       -o /out/gitleaks github.com/zricethezav/gitleaks/v8

FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40 AS tool
COPY --from=build /out/gitleaks /usr/local/bin/gitleaks
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
