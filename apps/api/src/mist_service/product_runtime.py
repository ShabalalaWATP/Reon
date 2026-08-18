"""Explicit managed-product composition contract for the application root."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from mist_service.product_clamav import (
    ClamAvInstreamScanner,
    CompositeDocumentScanner,
)
from mist_service.product_ports import (
    DocumentScanner,
    ExternalLinkPolicy,
    PrivateObjectStorage,
    ScannerAssurance,
)
from mist_service.product_quota_policy import (
    MAX_GLOBAL_STORAGE_BYTES,
    MAX_REQUEST_STORAGE_BYTES,
    MAX_USER_STORAGE_BYTES,
)
from mist_service.product_security import (
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
    SafeDocumentScanner,
)


@dataclass(frozen=True, slots=True)
class ProductRuntime:
    storage: PrivateObjectStorage
    scanner: DocumentScanner
    link_policy: ExternalLinkPolicy
    upload_ttl: timedelta = timedelta(minutes=10)
    maximum_file_bytes: int = MAX_FILE_BYTES
    maximum_package_bytes: int = MAX_PACKAGE_BYTES
    maximum_request_storage_bytes: int = MAX_REQUEST_STORAGE_BYTES
    maximum_user_storage_bytes: int = MAX_USER_STORAGE_BYTES
    maximum_global_storage_bytes: int = MAX_GLOBAL_STORAGE_BYTES
    managed_file_uploads_enabled: bool = True
    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 30.0

    @property
    def scanner_assurance(self) -> ScannerAssurance:
        return self.scanner.assurance

    @property
    def approved_semantic_cdr(self) -> bool:
        return self.scanner_assurance is ScannerAssurance.APPROVED_SEMANTIC_CDR


def clamav_product_runtime(
    storage: PrivateObjectStorage,
    link_policy: ExternalLinkPolicy,
    *,
    clamav_host: str,
    clamav_port: int = 3310,
    clamav_timeout_seconds: float = 30.0,
    upload_ttl: timedelta = timedelta(minutes=10),
    maximum_file_bytes: int = MAX_FILE_BYTES,
    maximum_package_bytes: int = MAX_PACKAGE_BYTES,
) -> ProductRuntime:
    malware = ClamAvInstreamScanner(
        clamav_host,
        port=clamav_port,
        timeout_seconds=clamav_timeout_seconds,
        maximum_bytes=maximum_file_bytes,
    )
    return ProductRuntime(
        storage=storage,
        scanner=CompositeDocumentScanner(
            SafeDocumentScanner(), malware, maximum_bytes=maximum_file_bytes
        ),
        link_policy=link_policy,
        upload_ttl=upload_ttl,
        maximum_file_bytes=maximum_file_bytes,
        maximum_package_bytes=maximum_package_bytes,
        clamav_host=clamav_host,
        clamav_port=clamav_port,
        clamav_timeout_seconds=clamav_timeout_seconds,
    )
