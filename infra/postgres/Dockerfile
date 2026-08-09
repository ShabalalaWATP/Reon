FROM postgres:17.10-alpine3.23@sha256:8189a1f6e40904781fc9e2612687877791d21679866db58b1de996b31fc312e4

# The official entrypoint only needs gosu when PID 1 starts as root. Local volume
# ownership is prepared by a bounded init service, so the database can run directly
# as the fixed postgres identity and the unused vulnerable helper can be removed.
RUN rm -f /usr/local/bin/gosu

COPY --chmod=0555 infra/postgres/init-databases.sh /docker-entrypoint-initdb.d/10-init-databases.sh

USER 70:70
