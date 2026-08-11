import { usePlatformClassification } from "../lib/platform/usePlatformClassification";

export function ClassificationBanner() {
  const setting = usePlatformClassification();
  const classification = setting.data?.classification ?? "OFFICIAL";
  return (
    <div
      aria-label={`Security classification: ${classification}`}
      className="classification-strip"
      data-classification={classification}
      role="note"
    >
      <span>{classification}</span>
    </div>
  );
}
