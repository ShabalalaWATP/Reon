import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { platformSecurityApi, type PlatformClassification } from "../../lib/api/platformSecurityClient";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { platformClassificationKey, usePlatformClassification } from "../../lib/platform/usePlatformClassification";

const options: PlatformClassification[] = [
  "OFFICIAL",
  "OFFICIAL-SENSITIVE",
  "SECRET",
  "TOP-SECRET",
];

export function ClassificationControl() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const setting = usePlatformClassification();
  const [selected, setSelected] = useState<PlatformClassification>("OFFICIAL");
  useEffect(() => {
    if (setting.data) setSelected(setting.data.classification);
  }, [setting.data]);
  const update = useMutation({
    mutationFn: (classification: PlatformClassification) =>
      platformSecurityApi.updateClassification(
        classification,
        setting.data!.version,
        session!.csrfToken,
      ),
    onSuccess: (saved) => queryClient.setQueryData(platformClassificationKey, saved),
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    update.mutate(selected);
  }
  const elevated = isSessionElevated(session);
  return (
    <section className="classification-control" aria-labelledby="classification-control-title">
      <div className="classification-control__copy">
        <ShieldCheck aria-hidden="true" size={18} />
        <div className="section-heading">
          <span>Global visual marking</span>
          <h2 id="classification-control-title">Platform classification</h2>
          <p className="field-hint">This label appears above every ISTARI page. It does not change request permissions or handling rules.</p>
        </div>
      </div>
      {setting.isError ? <p className="form-banner form-banner--error" role="alert">The classification setting could not be loaded.</p> : (
        <form onSubmit={submit}>
          <label className="form-field">
            <span>Classification</span>
            <select disabled={!elevated || setting.isPending || update.isPending} onChange={(event) => setSelected(event.target.value as PlatformClassification)} value={selected}>
              {options.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <button className="button button--primary" disabled={!elevated || setting.isPending || update.isPending || selected === setting.data?.classification} type="submit">
            {update.isPending ? "Applying…" : "Apply to everyone"}
          </button>
        </form>
      )}
      {update.isSuccess ? <p className="form-banner form-banner--success" role="status">Classification updated for every workspace.</p> : null}
      {update.isError ? <p className="form-banner form-banner--error" role="alert">The classification changed elsewhere or could not be saved. Refresh and try again.</p> : null}
    </section>
  );
}
