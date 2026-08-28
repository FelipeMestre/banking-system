"use client";

import { useEffect, useId, useRef } from "react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { X } from "lucide-react";
import { Button } from "./button";

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
 * Generic popup chrome on top of Radix's Dialog primitive — overlay,
 * header (title + close cross), body, and a Cancel/Accept footer — with
 * none of its own opinions about what it contains. Deliberately
 * entity-agnostic: a caller composes it with whatever form belongs inside
 * (see features/locations/components/AddLocationDialog.tsx for the
 * pattern), which is what makes the form part swappable without touching
 * this component at all.
 *
 * Radix's Dialog already provides the focus trap and Escape-to-close (and
 * closing on an outside click, which covers the overlay); the two pieces
 * still hand-rolled here are app-specific, not things Radix does by
 * default: Enter anywhere in the dialog means Accept, and the Accept
 * button gets focus on open only when nothing else already claimed it
 * (a form field's own autoFocus still wins).
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
  const acceptRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement;

      // Enter always means Accept, everywhere in the dialog — except inside a
      // textarea, where Enter has to stay a newline. Handled explicitly here
      // rather than left to a focused button's native activation, since that
      // depends on how faithfully the keyboard event was generated.
      if (event.key === "Enter" && target.tagName !== "TEXTAREA") {
        event.preventDefault();
        if (!acceptDisabled) onAccept();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onAccept, acceptDisabled]);

  return (
    <DialogPrimitive.Root open onOpenChange={(open) => !open && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[color-mix(in_srgb,var(--color-neutral-900)_50%,transparent)]" />
        {/*
          Radix portals Overlay and Content as siblings, not nested, and it
          forces an inline `pointer-events: auto` onto Content whenever it's
          open (its own focus/dismissable-layer management — a plain
          `pointer-events-none` class on Content can't win against that
          inline style, confirmed live). So Content can't be a full-viewport
          wrapper with "empty" clickable space around a centered child the
          way `.dialog-backdrop` used to be — any click in that empty space
          would read as "inside" the dialog and stop the overlay from
          closing it. Instead Content IS the visible box, sized to its
          content and centered by fixed positioning + transform, so there's
          no empty area to swallow a click in the first place.
        */}
        <DialogPrimitive.Content
          className="fixed top-1/2 left-1/2 z-50 flex w-[min(440px,100%)] max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col gap-ds-3 rounded-lg bg-surface p-ds-4 shadow-lg"
          aria-labelledby={titleId}
          onOpenAutoFocus={(event) => {
            // A form field's own autoFocus (see LocationForm etc.) already
            // won by the time this fires — only step in when nothing
            // claimed focus, so Enter has an Accept button to reach.
            const content = event.currentTarget as HTMLElement;
            if (!content.querySelector("[autofocus]")) {
              event.preventDefault();
              acceptRef.current?.focus();
            }
          }}
        >
          <div className="flex items-start justify-between">
            <DialogPrimitive.Title id={titleId} className="font-heading text-[20px] font-extrabold">
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <Button type="button" variant="ghost" size="icon" aria-label="Close">
                <X size={18} />
              </Button>
            </DialogPrimitive.Close>
          </div>

          <div className="text-sm opacity-85">{children}</div>

          <div className="mt-ds-2 flex justify-end gap-ds-2">
            <Button type="button" variant="outline" onClick={onClose}>
              {cancelLabel}
            </Button>
            <Button ref={acceptRef} type="button" onClick={onAccept} disabled={acceptDisabled}>
              {acceptLabel}
            </Button>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
