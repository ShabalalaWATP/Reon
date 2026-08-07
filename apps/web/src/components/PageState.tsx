import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

type PageStateProps = {
  kind: "loading" | "empty" | "error";
  title: string;
  children?: ReactNode;
  action?: ReactNode;
};

export function PageState({ action, children, kind, title }: PageStateProps) {
  const Icon = kind === "loading" ? LoaderCircle : kind === "error" ? AlertCircle : Inbox;
  return (
    <section className={`page-state page-state--${kind}`} aria-live="polite">
      <Icon aria-hidden="true" className={kind === "loading" ? "spin" : ""} size={24} />
      <div>
        <h2>{title}</h2>
        {children ? <p>{children}</p> : null}
      </div>
      {action}
    </section>
  );
}
