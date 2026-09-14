import { Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  onCreateClick: () => void;
}

/**
 * Shown only when `GET /accounts` succeeds with an empty `items` array (spec
 * — empty-state visibility). Fetch failures, 401s, and network errors keep
 * showing the existing error state instead — this component never renders
 * for those.
 */
export function NoAccountsEmptyState({ onCreateClick }: Props) {
  return (
    <div className="flex flex-col items-center gap-ds-3 rounded-lg border border-border bg-surface p-ds-8 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-accent-100 text-accent-700">
        <Wallet size={24} />
      </div>
      <h2 className="font-heading text-lg font-bold">You don&apos;t have any accounts yet</h2>
      <p className="m-0 max-w-[360px] text-sm text-neutral-600">
        Open your first account to start sending and receiving money. It only takes a moment.
      </p>
      <Button type="button" onClick={onCreateClick}>
        Create an account
      </Button>
    </div>
  );
}
