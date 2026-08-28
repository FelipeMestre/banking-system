import { CircleAlert } from "lucide-react";
import { DS_ICON_PROPS } from "@/lib/icon-props";

interface Props {
  message: string;
}

/** An operation-level failure inside a popup — a rejected save, a blocked delete. */
export function ErrorMessage({ message }: Props) {
  return (
    <p className="alert-error" role="alert">
      <CircleAlert size={16} {...DS_ICON_PROPS} />
      <span>{message}</span>
    </p>
  );
}
