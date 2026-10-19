FROM camunda/camunda:8.9.23@sha256:c25a3ffcd318dc00e4f8bb90c5b6af54d623cca890e4e7dd6189a1b8978142be

USER 0:0

# This deployment supports PostgreSQL only. Remove optional SQL Server and unused
# archive/HTTP utility components so their vulnerabilities are not reachable or
# present in the derived runtime inventory.
RUN rm -f \
    /usr/local/camunda/lib/mssql-jdbc-13.2.1.jre11.jar \
    /usr/bin/tar /usr/sbin/tar /usr/libexec/rmt /usr/sbin/wget \
    /usr/lib/libnghttp2.so* \
    /var/lib/db/sbom/gnutar-*.spdx.json \
    /var/lib/db/sbom/gnutar-rmt-*.spdx.json \
    /var/lib/db/sbom/libnghttp2-14-*.spdx.json

# Upgrade the base shell package to the repository's patched release.
RUN apk add --no-cache 'busybox>=1.38.0-r1'

COPY --chown=1001:0 infra/camunda/application-postgresql.yaml /usr/local/camunda/config/application.yaml

USER 1001:1001
