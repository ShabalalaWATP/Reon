import { ExternalLink } from "lucide-react";
import { useState, type FormEvent } from "react";

export type ExternalLinkDraft = { expiresAt?: string; label: string; url: string };

export function ExternalLinkForm({
  disabled,
  onAdd,
}: {
  disabled: boolean;
  onAdd: (draft: ExternalLinkDraft) => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const draft = {
      expiresAt: String(data.get("expiresAt") ?? "") || undefined,
      label: String(data.get("label") ?? "").trim(),
      url: String(data.get("url") ?? "").trim(),
    };
    const validation = validateLink(draft);
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);
    setPending(true);
    try {
      await onAdd({
        ...draft,
        expiresAt: draft.expiresAt ? new Date(draft.expiresAt).toISOString() : undefined,
      });
      event.currentTarget.reset();
    } catch (linkError) {
      setError(
        linkError instanceof Error ? linkError.message : "The product link could not be added.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="product-entry-form" onSubmit={(event) => void submit(event)} noValidate>
      <div className="section-heading">
        <span>Approved destination</span>
        <h3>Link to an external product</h3>
      </div>
      <label className="form-field">
        <span>Product label</span>
        <input disabled={disabled || pending} maxLength={160} name="label" />
      </label>
      <label className="form-field">
        <span>HTTPS product URL</span>
        <input
          autoComplete="url"
          disabled={disabled || pending}
          name="url"
          placeholder="https://approved.example.test/product"
          type="url"
        />
      </label>
      <label className="form-field">
        <span>Expiry (optional)</span>
        <input disabled={disabled || pending} name="expiresAt" type="datetime-local" />
      </label>
      {error ? (
        <p className="form-banner form-banner--error" role="alert">
          {error}
        </p>
      ) : null}
      <button className="button button--primary" disabled={disabled || pending} type="submit">
        <ExternalLink aria-hidden="true" size={16} />
        {pending ? "Checking link…" : "Add approved link"}
      </button>
      <p className="product-assurance">
        ISTARI records the destination domain but never fetches or previews its content.
      </p>
    </form>
  );
}

function validateLink(draft: ExternalLinkDraft) {
  if (!draft.label) return "Enter a product label.";
  try {
    const url = new URL(draft.url);
    if (url.protocol !== "https:" || url.username || url.password || url.hash) {
      return "Use an absolute HTTPS URL without credentials or a fragment.";
    }
    if (["localhost", "127.0.0.1", "::1"].includes(url.hostname.toLowerCase())) {
      return "Local destinations are not permitted.";
    }
  } catch {
    return "Enter a valid absolute HTTPS URL.";
  }
  return null;
}
