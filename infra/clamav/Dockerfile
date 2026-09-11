# syntax=docker/dockerfile-upstream:master@sha256:655d8ec53fd4a740c5e5a7031454a72020caf93841bad4a9f7f4f4d85929c083

FROM clamav/clamav:1.5.4@sha256:78810772a92b4a9168115bc6b2e0ffd702640893b9577f8c3d0432762d2655c4

RUN sed -i \
        -e 's|^LogFile .*|LogFile /tmp/clamd.log|' \
        /etc/clamav/clamd.conf && \
    sed -i \
        -e 's|^UpdateLogFile .*|UpdateLogFile /tmp/freshclam.log|' \
        -e '/^NotifyClamd /d' \
        /etc/clamav/freshclam.conf

COPY --chmod=0555 infra/clamav/healthcheck.sh /usr/local/bin/mist-clamav-healthcheck

USER 100:101
ENTRYPOINT ["/init-unprivileged"]

HEALTHCHECK --start-period=5m --interval=1m --timeout=5s --retries=3 \
    CMD ["mist-clamav-healthcheck"]
