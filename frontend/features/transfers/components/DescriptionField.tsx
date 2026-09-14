"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function DescriptionField({ value, onChange }: Props) {
  return (
    <div className="field">
      <Label htmlFor="transfer-description">Description</Label>
      <Input
        id="transfer-description"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Optional"
        autoComplete="off"
        maxLength={200}
      />
    </div>
  );
}
