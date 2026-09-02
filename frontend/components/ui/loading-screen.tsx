import { cn } from "@/lib/utils";

export interface LoadingScreenProps {
  message?: string;
  fullScreen?: boolean;
  "data-testid"?: string;
}

const DEFAULT_MESSAGE = "Loading your accounts securely";

export function LoadingScreen({
  message = DEFAULT_MESSAGE,
  fullScreen = true,
  "data-testid": dataTestId,
}: LoadingScreenProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={message}
      data-slot="loading-screen"
      data-testid={dataTestId}
      className={cn(
        "flex flex-col items-center justify-center gap-ds-3 bg-bg p-ds-8 text-neutral-700 animate-[ob-fade-in_0.2s_ease-out]",
        fullScreen ? "min-h-screen" : "min-h-[240px]"
      )}
    >
      <div className="flex items-center gap-ds-3">
        <div
          aria-hidden="true"
          className="h-3.5 w-3.5 rounded-none bg-accent"
        />
        <span className="font-heading text-lg font-extrabold tracking-tight text-text">
          OpenBank
        </span>
      </div>

      <div
        aria-hidden="true"
        className="h-8 w-8 rounded-none border-[3px] border-neutral-300 border-t-accent animate-[ob-spin_0.8s_linear_infinite]"
      />

      <p className="text-sm text-neutral-700">{message}</p>

      <div
        aria-hidden="true"
        className="h-1 w-24 overflow-hidden rounded-none bg-neutral-300"
      >
        <div
          aria-hidden="true"
          className="h-full w-[30%] bg-accent animate-[ob-sweep_1.1s_ease-in-out_infinite]"
        />
      </div>

      <span className="sr-only">{message}</span>
    </div>
  );
}
