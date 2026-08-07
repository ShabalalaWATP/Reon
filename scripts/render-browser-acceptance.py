"""Validate Playwright CLI evidence and render final HTML and JUnit reports."""

# ruff: noqa: E501 - HTML is intentionally kept as a readable literal template.

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "output" / "playwright"
MANIFEST = EVIDENCE / "browser-acceptance.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    journeys = data.get("full_staff_journeys")
    if not isinstance(journeys, list) or len(journeys) != 2:
        raise ValueError("Exactly two non-Chrome full staff journeys are required")
    return data


def validate_journey(journey: dict[str, Any]) -> None:
    if journey.get("result") != "passed":
        raise ValueError(f"Journey did not pass: {journey.get('browser')}")
    for key in ("trace", "screenshot", "product"):
        path = EVIDENCE / str(journey[key])
        if not path.is_file():
            raise FileNotFoundError(path)
        expected = str(journey[f"{key}_sha256"])
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"Hash mismatch for {path.name}: {actual}")


def render_junit(data: dict[str, Any]) -> None:
    journeys: list[dict[str, Any]] = data["full_staff_journeys"]
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": "ISTARI cross-browser staff acceptance",
            "tests": str(len(journeys)),
            "failures": "0",
            "errors": "0",
            "skipped": "0",
            "timestamp": "2026-08-07T07:43:38Z",
        },
    )
    properties = ElementTree.SubElement(suite, "properties")
    for name, value in data["environment"].items():
        ElementTree.SubElement(
            properties, "property", {"name": name, "value": str(value)}
        )
    for journey in journeys:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            {
                "classname": "acceptance.full_staff_workflow",
                "name": f"{journey['browser']} {journey['request']}",
            },
        )
        details = (
            f"browser={journey['browser']} {journey['version']}\n"
            f"request={journey['request']}\nroute={journey['route']}\n"
            f"analyst={journey['analyst']}\nfeedback={journey['feedback_rating']}\n"
            f"clarification_messages={journey['clarification_messages']}\n"
            f"trace={journey['trace']}\ntrace_sha256={journey['trace_sha256']}"
        )
        ElementTree.SubElement(case, "system-out").text = details
    tree = ElementTree.ElementTree(suite)
    ElementTree.indent(tree, space="  ")
    tree.write(
        EVIDENCE / "cross-browser-staff-acceptance.junit.xml",
        encoding="utf-8",
        xml_declaration=True,
    )


def render_html(data: dict[str, Any]) -> None:
    rows = []
    for journey in data["full_staff_journeys"]:
        cells = [
            f"{journey['browser']} {journey['version']}",
            journey["request"],
            journey["route"],
            journey["analyst"],
            str(journey["clarification_messages"]),
            str(journey["feedback_rating"]),
            journey["result"].upper(),
        ]
        rows.append(
            "<tr>"
            + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells)
            + "</tr>"
        )
    scenarios = "".join(
        f"<li>{html.escape(str(scenario))}</li>" for scenario in data["scenarios"]
    )
    document = f"""<!doctype html>
<html lang="en-GB">
<head><meta charset="utf-8"><title>ISTARI cross-browser acceptance</title>
<style>
body{{font:16px/1.5 system-ui;margin:2rem;max-width:1100px;color:#17202a}}
h1{{margin-bottom:.25rem}} .pass{{color:#08783e;font-weight:700}}
table{{border-collapse:collapse;width:100%;margin:1.5rem 0}} th,td{{border:1px solid #bac4ce;padding:.6rem;text-align:left}}
th{{background:#eef3f6}} code{{overflow-wrap:anywhere}} .meta{{color:#425466}}
</style></head>
<body><main>
<h1>ISTARI cross-browser staff acceptance</h1>
<p class="pass">PASS: 2 complete state-changing journeys, 0 failures.</p>
<p class="meta">Recorded 7 August 2026 against React, FastAPI, PostgreSQL 17.9 and Camunda 8.9.14.</p>
<table><thead><tr><th>Browser</th><th>Request</th><th>Route</th><th>Analyst</th><th>Clarification messages</th><th>Feedback</th><th>Result</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<h2>Actions proved in each complete journey</h2>
<ol><li>Mandatory Customer submission and tracking.</li><li>JIOC, command and Ops routing with named claims and decisions.</li><li>Team Manager assignment to the selected team's Analyst.</li><li>Analyst clarification, Customer response and same-Analyst return.</li><li>Product submission, Manager approval, independent QC and dissemination.</li><li>Authenticated product download and one-time required feedback.</li></ol>
<h2>Combined acceptance suite</h2><ul>{scenarios}</ul>
<h2>Integrity</h2>
<p>Every trace, completion screenshot and downloaded product was SHA-256 verified before this report was generated. Exact values are retained in <code>browser-acceptance.json</code>.</p>
</main></body></html>"""
    (EVIDENCE / "cross-browser-staff-acceptance.html").write_text(
        document, encoding="utf-8"
    )


def main() -> None:
    data = load_manifest()
    for journey in data["full_staff_journeys"]:
        validate_journey(journey)
    render_junit(data)
    render_html(data)
    print("Browser acceptance report passed: 2 journeys, 0 failures")


if __name__ == "__main__":
    main()
