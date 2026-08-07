import { FileUp, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

const mediaTypes: Record<string, string> = {
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".pdf": "application/pdf",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
};

export type ManagedUpload = {
  file: File;
  label: string;
  mediaType: string;
  sha256: string;
};

export function ManagedFileForm({
  disabled,
  onUpload,
}: {
  disabled: boolean;
  onUpload: (upload: ManagedUpload) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const extension = file ? extensionOf(file.name) : "";
    if (!file || !mediaTypes[extension]) {
      setError("Choose a PDF, DOCX or PPTX file.");
      return;
    }
    if (!label.trim()) {
      setError("Enter a product label.");
      return;
    }
    setError(null);
    setPreparing(true);
    try {
      await onUpload({
        file,
        label: label.trim(),
        mediaType: mediaTypes[extension],
        sha256: await sha256(file),
      });
      setFile(null);
      setLabel("");
      event.currentTarget.reset();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "The file could not be uploaded.");
    } finally {
      setPreparing(false);
    }
  }

  return (
    <form className="product-entry-form" onSubmit={(event) => void submit(event)} noValidate>
      <div className="section-heading"><span>Managed file</span><h3>Upload for scanning</h3></div>
      <label className="form-field"><span>Product label</span><input disabled={disabled || preparing} maxLength={160} onChange={(event) => setLabel(event.target.value)} value={label} /></label>
      <label className="product-file-field">
        <FileUp aria-hidden="true" size={21} />
        <span><strong>{file?.name ?? "Choose PDF, Word or PowerPoint"}</strong><small>One approved file, no legacy or macro-enabled formats</small></span>
        <input accept=".pdf,.docx,.pptx" disabled={disabled || preparing} onChange={(event) => setFile(event.target.files?.[0] ?? null)} type="file" />
      </label>
      {error ? <p className="form-banner form-banner--error" role="alert">{error}</p> : null}
      <button className="button button--primary" disabled={disabled || preparing} type="submit">{preparing ? "Preparing secure upload…" : "Upload artefact"}</button>
      <p className="product-assurance"><ShieldCheck aria-hidden="true" size={15} />Review stays blocked until scanning reports a clean result.</p>
    </form>
  );
}

function extensionOf(filename: string) {
  const index = filename.lastIndexOf(".");
  return index < 0 ? "" : filename.slice(index).toLowerCase();
}

async function sha256(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
