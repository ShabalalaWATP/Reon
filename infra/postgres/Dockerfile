# syntax=docker/dockerfile:1.7

FROM postgres:17.10-alpine3.23@sha256:8189a1f6e40904781fc9e2612687877791d21679866db58b1de996b31fc312e4 AS vector-build

ADD --checksum=sha256:a9094dfb85ccdde3cbb295f1086d4c71a20db1d26bf1d6c39f07a7d164033eb4 \
    https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.1.tar.gz \
    /tmp/pgvector.tar.gz

RUN apk add --no-cache --virtual .vector-build-deps \
        build-base \
    && mkdir /tmp/pgvector \
    && tar -xzf /tmp/pgvector.tar.gz --strip-components=1 -C /tmp/pgvector \
    && make -C /tmp/pgvector OPTFLAGS="" with_llvm=no \
    && make -C /tmp/pgvector install with_llvm=no \
    && mkdir -p /usr/share/doc/pgvector \
    && cp /tmp/pgvector/LICENSE /tmp/pgvector/README.md /usr/share/doc/pgvector/

FROM postgres:17.10-alpine3.23@sha256:8189a1f6e40904781fc9e2612687877791d21679866db58b1de996b31fc312e4

COPY --from=vector-build /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/vector.so
COPY --from=vector-build /usr/local/share/postgresql/extension/vector* /usr/local/share/postgresql/extension/
COPY --from=vector-build /usr/share/doc/pgvector /usr/share/doc/pgvector

# PID 1 starts as the fixed postgres identity after a bounded init service has
# prepared volume ownership, so the unused privilege-transition helper is removed.
RUN rm -f /usr/local/bin/gosu

COPY --chmod=0555 infra/postgres/init-databases.sh /docker-entrypoint-initdb.d/10-init-databases.sh

USER 70:70
