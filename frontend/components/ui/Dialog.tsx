"use client";

import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";
import { DS_ICON_PROPS } from "@/lib/icon-props";

interface Props {
  title: string;
  /** Overlay click, the close cross, Escape, and the Cancel button all mean the same thing. */
  onClose: () => void;
  /** The Accept button and Enter (outside a button/textarea) both mean the same thing. */
  onAccept: () => void;
  acceptLabel?: string;
  cancelLabel?: string;
  /** Purely disables the Accept button — validity itself is the caller's business. */
  acceptDisabled?: boolean;
  /** The form (or whatever else) this popup wraps. Swap it out to reuse this chrome for another entity. */
  children: React.ReactNode;
}

/**
 * Generic Modernist popup chrome — overlay, header (title + close cross),
 * body, and a Cancel/Accept footer — with none of its own opinions about
 * what it contains. Deliberately entity-agnostic: a caller composes it with
 * whatever form belongs inside (see features/locations/components/
 * AddLocationDialog.tsx for the pattern), which is what makes the form part
 * swappable without touching this component at all.
 */
export function Dialog({
  title,
  onClose,
  onAccept,
  acceptLabel = "Accept",
  cancelLabel = "Cancel",
  acceptDisabled = false,
  children,
}: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      const target = event.target as HTMLElement;

      // A button already does its own thing on Enter (activates itself,
      // whichever one has focus) — only hijack Enter when it isn't that, and
      // never inside a textarea, where Enter has to stay a newline.
      if (event.key === "Enter" && target.tagName !== "TEXTAREA" && target.tagName !== "BUTTON") {
        event.preventDefault();
        onAccept();
        return;
      }

      if (event.key === "Tab") {
        const node = dialogRef.current;
        if (!node) return;
        const focusable = getFocusable(node);
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!first || !last) return;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, onAccept]);

  return (
    <div
      className="dialog-backdrop"
      onClick={(event) => {
        // Only the backdrop itself closes the popup — a click that bubbled
        // up from inside the dialog box must not.
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="flex items-start justify-between">
          <h2 id={titleId} className="dialog-title">
            {title}
          </h2>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Close" onClick={onClose}>
            <X size={18} {...DS_ICON_PROPS} />
          </button>
        </div>

        <div className="dialog-body">{children}</div>

        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            {cancelLabel}
          </button>
          <button type="button" className="btn btn-primary" onClick={onAccept} disabled={acceptDisabled}>
            {acceptLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function getFocusable(container: HTMLElement): HTMLElement[] {
  const selector =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  return Array.from(container.querySelectorAll<HTMLElement>(selector));
}
