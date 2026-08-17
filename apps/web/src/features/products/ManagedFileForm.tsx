import { FileUp, ShieldCheck } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import {
  managedUploadStageLabel,
  type ManagedUpload,
  type ManagedUploadProgress,
} from "./managedUploadModel";

const mediaTypes: Record<string, string> = {
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
};

export function ManagedFileForm({
  disabled,
  maximumFiles = 10,
  onRetry,
  onUpload,
  progress = [],
  uploading = false,
}: {
  disabled: boolean;
  maximumFiles?: number;
  onRetry?: () => Promise<void>;
  onUpload: (uploads: ManagedUpload[]) => Promise<void>;
  progress?: readonly ManagedUploadProgress[];
  uploading?: boolean;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [label, setLabel] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unfinished = progress.some((upload) => upload.stage !== "complete");
  const busy = anyTrue(preparing, uploading);
  const controlsDisabled = anyTrue(disabled, busy, unfinished);
  const actionDisabled = anyTrue(disabled, busy);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (files.length === 0 || files.some((file) => !mediaTypes[extensionOf(file.name)])) {
      setError("Choose PDF, DOCX, PPTX, PNG or JPEG files.");
      return;
    }
    if (files.length > maximumFiles) {
      setError(`Choose no more than ${maximumFiles} files for this package.`);
      return;
    }
    if (files.length === 1 && !label.trim()) {
      setError("Enter a product label.");
      return;
    }
    setError(null);
    setPreparing(true);
    try {
      const uploads = await Promise.all(
        files.map(async (file) => ({
          file,
          label: files.length === 1 ? label.trim() : labelFor(file),
          mediaType: mediaTypes[extensionOf(file.name)],
          sha256: await sha256(file),
        })),
      );
      await onUpload(uploads);
      setFiles([]);
      setLabel("");
      form.reset();
    } catch (uploadError) {
      setError(
        uploadError instanceof Error ? uploadError.message : "The file could not be uploaded.",
      );
    } finally {
      setPreparing(false);
    }
  }

  async function retry() {
    if (!onRetry) return;
    setError(null);
    setPreparing(true);
    try {
      await onRetry();
      clearSelection();
    } catch (uploadError) {
      setError(
        uploadError instanceof Error ? uploadError.message : "The file could not be uploaded.",
      );
    } finally {
      setPreparing(false);
    }
  }

  function clearSelection() {
    setFiles([]);
    setLabel("");
    formRef.current?.reset();
  }

  return (
    <form
      className="product-entry-form"
      onSubmit={(event) => void submit(event)}
      noValidate
      ref={formRef}
    >
      <div className="section-heading">
        <span>Managed file</span>
        <h3>Upload product to MIST</h3>
      </div>
      <ProductLabelField
        disabled={controlsDisabled}
        files={files}
        label={label}
        onChange={setLabel}
      />
      <FileSelectionField
        disabled={controlsDisabled}
        files={files}
        maximumFiles={maximumFiles}
        onChange={setFiles}
      />
      <UploadProgressList progress={progress} />
      <UploadError error={error} />
      <UploadAction
        disabled={actionDisabled}
        onRetry={availableRetry(onRetry, retry)}
        retrying={busy}
        unfinished={unfinished}
      />
      <p className="product-assurance">
        <ShieldCheck aria-hidden="true" size={15} />
        Review stays blocked until scanning reports a clean result.
      </p>
    </form>
  );
}

function ProductLabelField({
  disabled,
  files,
  label,
  onChange,
}: {
  disabled: boolean;
  files: File[];
  label: string;
  onChange: (label: string) => void;
}) {
  const suffix = files.length > 1 ? "(created from each filename)" : "";
  return (
    <label className="form-field">
      <span>Product label {suffix}</span>
      <input
        disabled={disabled || files.length > 1}
        maxLength={160}
        onChange={(event) => onChange(event.target.value)}
        value={label}
      />
    </label>
  );
}

function FileSelectionField({
  disabled,
  files,
  maximumFiles,
  onChange,
}: {
  disabled: boolean;
  files: File[];
  maximumFiles: number;
  onChange: (files: File[]) => void;
}) {
  return (
    <label className="product-file-field">
      <FileUp aria-hidden="true" size={21} />
      <span>
        <strong>{fileSelectionLabel(files.length)}</strong>
        <small>Up to {maximumFiles} PDF, Word, PowerPoint, PNG or JPEG files</small>
      </span>
      <input
        accept=".pdf,.docx,.pptx,.png,.jpg,.jpeg"
        disabled={disabled}
        multiple
        onChange={(event) => onChange(Array.from(event.target.files ?? []))}
        type="file"
      />
    </label>
  );
}

function UploadProgressList({ progress }: { progress: readonly ManagedUploadProgress[] }) {
  if (progress.length === 0) return null;
  return (
    <ul
      aria-label="Upload progress"
      aria-live="polite"
      className="managed-upload-progress product-artefact-list"
    >
      {progress.map((upload) => (
        <li key={upload.createIdempotencyKey}>
          <span className="product-artefact-copy">
            <strong>{upload.draft.file.name}</strong>
            <small>{managedUploadStageLabel(upload)}</small>
          </span>
          <UploadRetryState upload={upload} />
        </li>
      ))}
    </ul>
  );
}

function UploadRetryState({ upload }: { upload: ManagedUploadProgress }) {
  if (upload.stage !== "error") return null;
  return (
    <span className="product-inline-state product-inline-state--error" role="alert">
      Needs retry
    </span>
  );
}

function UploadError({ error }: { error: string | null }) {
  if (!error) return null;
  return (
    <p className="form-banner form-banner--error" role="alert">
      {error}
    </p>
  );
}

function UploadAction({
  disabled,
  onRetry,
  retrying,
  unfinished,
}: {
  disabled: boolean;
  onRetry?: () => Promise<void>;
  retrying: boolean;
  unfinished: boolean;
}) {
  if (unfinished && onRetry) {
    return (
      <button
        className="button button--primary"
        disabled={disabled}
        onClick={() => void onRetry()}
        type="button"
      >
        {retrying ? "Retrying secure upload…" : "Retry unfinished uploads"}
      </button>
    );
  }
  return (
    <button className="button button--primary" disabled={disabled} type="submit">
      {retrying ? "Preparing secure upload…" : "Upload to MIST"}
    </button>
  );
}

function fileSelectionLabel(count: number) {
  if (count === 0) return "Choose documents or images";
  return `${count} file${count === 1 ? "" : "s"} selected`;
}

function anyTrue(...values: boolean[]) {
  return values.includes(true);
}

function availableRetry(onRetry: (() => Promise<void>) | undefined, retry: () => Promise<void>) {
  return onRetry ? retry : undefined;
}

function labelFor(file: File) {
  const extension = extensionOf(file.name);
  return file.name.slice(0, file.name.length - extension.length).slice(0, 160);
}

function extensionOf(filename: string) {
  const index = filename.lastIndexOf(".");
  return index < 0 ? "" : filename.slice(index).toLowerCase();
}

async function sha256(file: File) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
