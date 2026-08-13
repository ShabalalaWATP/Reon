# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM clamav/clamav:1.5.3@sha256:d06c1d6a451d616e1dd79b42f44c8c8c291bba9cf4e75ebc4d0e43c1c6dd87bb

RUN sed -i \
        -e 's|^LogFile .*|LogFile /tmp/clamd.log|' \
        /etc/clamav/clamd.conf && \
    sed -i \
        -e 's|^UpdateLogFile .*|UpdateLogFile /tmp/freshclam.log|' \
        -e '/^NotifyClamd /d' \
        /etc/clamav/freshclam.conf

COPY --chmod=0555 infra/clamav/healthcheck.sh /usr/local/bin/istari-clamav-healthcheck

USER 100:101
ENTRYPOINT ["/init-unprivileged"]

HEALTHCHECK --start-period=5m --interval=1m --timeout=5s --retries=3 \
    CMD ["istari-clamav-healthcheck"]
