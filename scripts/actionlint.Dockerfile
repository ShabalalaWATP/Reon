# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM golang:1.26.5-alpine3.23@sha256:622e56dbc11a8cfe87cafa2331e9a201877271cbff918af53d3be315f3da88cc AS build
RUN GOBIN=/out go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12

FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40
COPY --from=build /out/actionlint /usr/local/bin/actionlint
WORKDIR /repo
ENTRYPOINT ["actionlint"]
