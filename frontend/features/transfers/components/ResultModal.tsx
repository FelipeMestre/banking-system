"use client";

import Link from "next/link";
import { Dialog as DialogPrimitive } from "radix-ui";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { TransferResult } from "../hooks/useTransferDraft";

interface Props {
  result: TransferResult;
  onClose: () => void;
}

export function ResultModal({ result, onClose }: Props) {
  if (result === null) return null;
  const isSuccess = result.kind === "success";

  return (
    <DialogPrimitive.Root open onOpenChange={(open) => !open && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[color-mix(in_srgb,var(--color-neutral-900)_55%,transparent)]" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed top-1/2 left-1/2 z-50 flex w-[min(440px,100%)] max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-ds-4 rounded-none bg-surface p-ds-6 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out"
          style={{ animation: "ob-scale 0.2s ease-out" }}
        >
          <DialogPrimitive.Close asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Close"
              className="absolute right-ds-2 top-ds-2"
              onClick={onClose}
            >
              <X size={18} />
            </Button>
          </DialogPrimitive.Close>

          <div
            data-testid="result-icon"
            className={
              "flex h-[72px] w-[72px] items-center justify-center rounded-full border-3 " +
              (isSuccess
                ? "border-[#12813f] text-[#12813f]"
                : "border-accent-700 text-accent-700")
            }
          >
            {isSuccess ? <Check size={36} /> : <X size={36} />}
          </div>

          <DialogPrimitive.Title className="font-heading text-[20px] font-extrabold">
            {isSuccess ? "Success in the operation" : "Error in the operation"}
          </DialogPrimitive.Title>

          <p className="m-0 text-center text-sm text-neutral-600">
            {isSuccess
              ? "Your transfer was completed successfully."
              : result.message || "Your transfer could not be completed."}
          </p>

          <div className="mt-ds-2 flex w-full justify-center">
            {isSuccess ? (
              <Button asChild>
                <Link href="/">Go to Homepage</Link>
              </Button>
            ) : (
              <Button type="button" onClick={onClose}>
                Try again
              </Button>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
