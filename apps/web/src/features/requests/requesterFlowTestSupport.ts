import { fireEvent, screen } from "@testing-library/react";

export function releasedPackage(requestId: string) {
  return {
    packageId: "released-package",
    requestId,
    packageVersion: 1,
    status: "DISSEMINATED",
    releasedAt: "2026-08-06T11:00:00Z",
    releasedBy: "QC Manager",
    coveringNote: "Synthetic note to the Customer.",
    acceptedAt: null,
    artefacts: [
      {
        id: "released-file",
        packageId: "released-package",
        position: 1,
        kind: "MANAGED_FILE",
        lifecycle: "RELEASED",
        label: "Readiness summary",
        filename: "readiness.pdf",
        mediaType: "application/pdf",
        sizeBytes: 2048,
        sha256: "a".repeat(64),
        version: 1,
        destinationDomain: null,
        expiresAt: null,
        scanResult: "CLEAN",
        scanReason: null,
        releasedAt: "2026-08-06T11:00:00Z",
      },
    ],
  };
}

export function fillRequestForm() {
  setField(/Request title/, "Quarterly service readiness summary");
  setField(/Description of the need/, "Provide a clear summary of current service readiness.");
  setField(/Specific question to answer/, "What does the evidence show about readiness?");
  setField(/Desired outcome/, "Leaders can make the next quarterly decision.");
  setField(/Background and known context/, "Quarterly review context.");
  setField(/Subject area or location/, "Synthetic service area");
  setField(/Relevant period starts/, "2026-09-01");
  setField(/Relevant period ends/, "2026-09-05");
  setField(/Activity, project or decision supported/, "The quarterly planning decision.");
  setField(/Latest useful delivery date/, "2026-09-10");
  setField(/Preferred product type/, "Briefing note");
  setField(/Why this date matters/, "The review is scheduled the following day.");
  setField(/Success criteria/, "All agreed measures and next steps are covered.");
  setField(/Constraints or caveats/, "No known constraints.");
  setField(/Supporting information available/, "No supporting material is available.");
  setField(/Handling instructions/, "Standard handling applies.");
}

function setField(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
