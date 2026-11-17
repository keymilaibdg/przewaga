import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { LuX } from "react-icons/lu";

/** Mobile bottom sheet (centered dialog on wide screens). */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Zamknij" className="animate-fade-in absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="animate-sheet-up pb-safe relative max-h-[85dvh] w-full max-w-lg overflow-hidden rounded-t-3xl border border-line-strong bg-ink-900 sm:rounded-3xl">
        <div className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-white/15 sm:hidden" />
        <div className="flex items-center justify-between px-5 pt-3 pb-2">
          <h3 className="text-base font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="grid size-10 place-items-center rounded-full text-fg-muted hover:bg-white/5" aria-label="Zamknij">
            <LuX className="size-5" />
          </button>
        </div>
        <div className="max-h-[calc(85dvh-4rem)] overflow-y-auto px-5 pb-6">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
