# syntax=docker/dockerfile:1.7

FROM trufflesecurity/trufflehog:3.96.0@sha256:aa821cf4ace8861c7d096d83818cdf7bb9719028a52d37a52eaad44086a52577 AS scan
WORKDIR /repo
COPY .git .git
RUN /usr/bin/trufflehog git file:///repo \
    --results=verified,unknown \
    --no-update \
    --json \
    > /tmp/trufflehog-git.json

FROM scan AS gate
RUN test ! -s /tmp/trufflehog-git.json

FROM scratch AS evidence
COPY --from=scan /tmp/trufflehog-git.json /trufflehog-git.json
