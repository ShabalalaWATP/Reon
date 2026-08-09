"""Hash and validate target-scale database and browser evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def build(args: argparse.Namespace) -> dict[str, Any]:
    fixture = _read(args.fixture)
    runtime = _read(args.runtime)
    browser = _read(args.measurements)
    http_load = _read(args.http_load)
    artefacts = sorted(
        path
        for path in args.artefact_dir.iterdir()
        if path.is_file() and path.suffix in {".network", ".png", ".trace"}
    )
    passed = bool(
        fixture.get("passed")
        and runtime.get("passed")
        and browser.get("all_scenarios_passed")
        and http_load.get("passed")
        and len(artefacts) == 12
    )
    return {
        "artefacts": {
            path.relative_to(args.output.parent.parent).as_posix(): {
                "bytes": path.stat().st_size,
                "sha256": _hash(path),
            }
            for path in artefacts
        },
        "browser_measurements_sha256": _hash(args.measurements),
        "fixture_sha256": _hash(args.fixture),
        "generated_at": datetime.now(UTC).isoformat(),
        "http_load_sha256": _hash(args.http_load),
        "passed": passed,
        "runtime_evidence_sha256": _hash(args.runtime),
        "target_rows": runtime.get("target_rows"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--measurements", type=Path, required=True)
    parser.add_argument("--http-load", type=Path, required=True)
    parser.add_argument("--artefact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
