"use client";

interface Props {
  isLoading: boolean;
}

export function ProcessingOverlay({ isLoading }: Props) {
  if (!isLoading) return null;
  return (
    <div
      data-testid="processing-overlay"
      aria-busy="true"
      aria-live="polite"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[color-mix(in_srgb,var(--color-neutral-900)_55%,transparent)]"
    >
      <div className="flex flex-col items-center gap-ds-3 rounded-none bg-surface p-ds-6 shadow-lg">
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-divider border-t-accent"
          aria-hidden="true"
        />
        <p className="m-0 font-heading text-sm font-extrabold">Processing your transfer</p>
      </div>
    </div>
  );
}
