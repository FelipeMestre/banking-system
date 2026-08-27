import { Lock } from "lucide-react";
import { DS_ICON_PROPS } from "@/lib/icon-props";

interface Props {
  greeting: string;
  lastSignIn: string;
}

/** Purely presentational: no state, so this stays a server component. */
export function Topbar({ greeting, lastSignIn }: Props) {
  return (
    <header className="flex h-[72px] flex-none items-center justify-between gap-ds-6 border-b-2 border-divider px-ds-8">
      <div className="flex min-w-0 items-baseline gap-[14px]">
        <h1 className="m-0 text-xl tracking-[-0.01em]">{greeting}</h1>
        <span className="whitespace-nowrap text-xs text-neutral-600">{lastSignIn}</span>
      </div>

      <div className="flex items-center gap-ds-6">
        <div className="flex items-center gap-ds-2 font-body text-[11px] font-semibold uppercase tracking-[0.1em] text-neutral-700">
          <Lock size={14} {...DS_ICON_PROPS} />
          Secured session
        </div>

        <div className="h-[28px] w-[2px] bg-divider" />

        <div className="flex items-center gap-[10px]">
          <div className="h-[14px] w-[14px] bg-accent" />
          <span className="font-heading text-[19px] font-extrabold tracking-[-0.02em]">OpenBank</span>
        </div>
      </div>
    </header>
  );
}
