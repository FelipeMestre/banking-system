import { CircleAlert } from "lucide-react";
import { Alert, AlertDescription } from "./alert";

interface Props {
  message: string;
}

/**
 * An operation-level failure inside a popup — a rejected save, a blocked
 * delete. Built on shadcn's Alert for its structure (icon+text grid,
 * role="alert"), with the red tint and text color painted on directly
 * rather than through the `destructive` variant: that variant only
 * reddens the text on the normal card background, not the background
 * itself, and its color rules target children by slot in a way a caller's
 * className can't cleanly override — simpler to just set the colors here.
 */
export function ErrorMessage({ message }: Props) {
  return (
    <Alert className="items-center gap-2 bg-accent-100 text-accent-700">
      <CircleAlert size={16} />
      <AlertDescription className="text-accent-700">{message}</AlertDescription>
    </Alert>
  );
}
