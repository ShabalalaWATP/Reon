import { useMutation } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";
import { useState } from "react";

import { statisticsEvolutionApi } from "../../lib/api/statisticsEvolutionClient";
import type {
  ExportPolicy,
  StatisticsEvolutionFilters,
  StatisticsExportResult,
} from "../../lib/api/statisticsEvolutionTypes";
import type { Session } from "../../lib/api/types";

export function StatisticsExportPanel({
  filters,
  policies,
  session,
}: {
  filters: StatisticsEvolutionFilters;
  policies: { csv: ExportPolicy; pdf: ExportPolicy };
  session: Session;
}) {
  const [result, setResult] = useState<StatisticsExportResult | null>(null);
  const mutation = useMutation({
    mutationFn: (format: "CSV" | "PDF") =>
      statisticsEvolutionApi.requestExport({ ...filters, format }, session.csrfToken),
    onSuccess: setResult,
  });
  return (
    <section className="statistics-export">
      <header><div><span>Audited aggregate output</span><h3>Controlled export</h3></div><p>The server repeats scope, date, cohort and suppression checks before producing a file.</p></header>
      <div className="statistics-export__actions">
        <ExportAction format="CSV" mutation={mutation} policy={policies.csv} />
        <ExportAction format="PDF" mutation={mutation} policy={policies.pdf} />
      </div>
      {mutation.isError ? <p role="alert">{errorMessage(mutation.error)}</p> : null}
      {result ? <ExportResult result={result} /> : null}
    </section>
  );
}

function ExportAction({
  format,
  mutation,
  policy,
}: {
  format: "CSV" | "PDF";
  mutation: UseMutationResult<StatisticsExportResult, Error, "CSV" | "PDF">;
  policy: ExportPolicy;
}) {
  const available = policy.state === "AVAILABLE";
  return (
    <div>
      <button className="button" disabled={!available || mutation.isPending} onClick={() => mutation.mutate(format)} type="button">Prepare {format}</button>
      <span>{available ? "Available for this aggregate scope" : `${policy.state}: ${policy.reason}`}</span>
    </div>
  );
}

function ExportResult({ result }: { result: StatisticsExportResult }) {
  const downloadUrl = safeDownloadUrl(result.downloadUrl);
  return (
    <div aria-live="polite" className="statistics-export__result">
      <strong>{result.state === "READY" ? "Export ready" : "Export pending"}</strong>
      <span>{result.message}</span>
      {result.state === "READY" && downloadUrl ? <a className="button button--primary" href={downloadUrl}>Download aggregate export</a> : null}
      {result.state === "READY" && result.downloadUrl && !downloadUrl ? <span>Download address rejected by the client safety policy.</span> : null}
    </div>
  );
}

function safeDownloadUrl(value: string | null) {
  return value?.startsWith("/api/v1/statistics/exports/") ? value : null;
}

function errorMessage(error: Error) {
  return error.message;
}
