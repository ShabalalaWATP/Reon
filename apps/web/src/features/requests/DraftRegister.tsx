import { FilePenLine } from "lucide-react";
import { Link } from "react-router";

import type { RequestDraft } from "../../lib/api/types";
import { formatDate } from "../../lib/status";

export function DraftRegister({ items }: { items: RequestDraft[] }) {
  if (items.length === 0) return null;
  return (
    <section className="register-section" aria-labelledby="draft-register-title">
      <header>
        <span>Private work</span>
        <h2 id="draft-register-title">Drafts</h2>
      </header>
      <div className="request-register">
        {items.map((draft) => (
          <Link
            className="request-row request-row--draft"
            key={draft.id}
            to={`/requests/drafts/${draft.id}`}
          >
            <span className="request-row__indicator" aria-hidden="true" />
            <FilePenLine aria-hidden="true" size={16} />
            <strong>{draft.title?.trim() || "Untitled request"}</strong>
            <span className="request-row__status">Draft</span>
            <span className="request-row__owner">Only visible to you</span>
            <time dateTime={draft.updatedAt}>Saved {formatDate(draft.updatedAt, true)}</time>
            <span className="request-row__open">Continue</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
