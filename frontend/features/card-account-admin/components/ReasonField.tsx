"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const REASON_MAX_LENGTH = 300;

/** Shared optional `reason` text field, `.field` (Label+Input) pattern, used
 * by every mutation dialog in this feature — every write endpoint accepts an
 * optional `reason?: string <=300`. */
export function ReasonField({
  value,
  onChange,
  id = "admin-action-reason",
}: {
  value: string;
  onChange: (value: string) => void;
  id?: string;
}) {
  return (
    <div className="field">
      <Label htmlFor={id}>Reason (optional)</Label>
      <Input
        id={id}
        value={value}
        maxLength={REASON_MAX_LENGTH}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Why is this action being taken?"
      />
    </div>
  );
}
