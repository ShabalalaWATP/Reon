import { type ReactNode, useEffect, useRef } from "react";

export function ModalDrawer({
  children,
  label,
  onClose,
  open,
}: {
  children: ReactNode;
  label: string;
  onClose: () => void;
  open: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!open || !element) return;
    returnFocus.current = document.activeElement as HTMLElement | null;
    if (typeof element.showModal === "function") element.showModal();
    else element.setAttribute("open", "");
    return () => {
      if (element.open && typeof element.close === "function") element.close();
      else element.removeAttribute("open");
      returnFocus.current?.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <dialog
      aria-label={label}
      className="modal-drawer"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
      ref={dialog}
    >
      <div className="modal-drawer__surface">
        <button aria-label={`Close ${label}`} className="modal-drawer__close" onClick={onClose} type="button">×</button>
        {children}
      </div>
    </dialog>
  );
}
