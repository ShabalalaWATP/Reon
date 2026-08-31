# syntax=docker/dockerfile-upstream:master@sha256:655d8ec53fd4a740c5e5a7031454a72020caf93841bad4a9f7f4f4d85929c083

FROM golang:1.27.0-alpine3.23@sha256:3747dcba41c8b0db3211fda4db61638b980e17ac5bb3c94460a975a9cfe19395 AS build
RUN GOBIN=/out go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12

FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40
COPY --from=build /out/actionlint /usr/local/bin/actionlint
WORKDIR /repo
ENTRYPOINT ["actionlint"]
