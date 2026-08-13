"""Interrupted and adversarial quarantine-index recovery regressions."""

from __future__ import annotations

import os

import pytest

from istari_service.product_filesystem_storage import PrivateFilesystemObjectStorage


def test_quarantine_index_resumes_an_already_staged_legacy_root(tmp_path) -> None:
    root = tmp_path / "private"
    legacy = root / "quarantine" / "legacy" / "object"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"source")
    storage = PrivateFilesystemObjectStorage(root)
    staged = root / ".quarantine-reconcile" / "legacy"
    staged.mkdir()
    (staged / "object").write_bytes(b"staged")

    storage._index._stage_one_legacy_root()

    assert legacy.read_bytes() == b"source"
    assert storage.reconcile_quarantine_index(limit=2) == 1
    assert legacy.read_bytes() == b"staged"


def test_quarantine_index_ignores_unsafe_and_non_regular_entries(tmp_path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO filesystem entries are not supported on this platform.")
    root = tmp_path / "private"
    storage = PrivateFilesystemObjectStorage(root)
    reconcile = root / ".quarantine-reconcile"
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    symlink = reconcile / "unsafe-link"
    try:
        symlink.symlink_to(outside)
    except OSError:
        pytest.skip("This account cannot create symbolic links.")
    nested = reconcile / "nested"
    nested.mkdir()
    fifo = nested / "non-regular"
    os.mkfifo(fifo)

    assert storage._index._recover_legacy(10) == 0
    assert symlink.is_symlink()
    assert fifo.exists()
    assert outside.read_bytes() == b"outside"
