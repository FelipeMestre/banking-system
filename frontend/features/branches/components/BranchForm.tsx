"use client";

import { useEffect, useState } from "react";
import { getLocations } from "@/features/locations";
import type { Location } from "@/features/locations";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface FieldErrors {
  code: string | null;
  name: string | null;
  locationId: string | null;
}

interface Props {
  code: string;
  name: string;
  locationId: string;
  onCodeChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onLocationIdChange: (value: string) => void;
  onFieldBlur: (field: keyof FieldErrors) => void;
  /** Only shown once a field has been touched, so the popup doesn't open already complaining. */
  errors: FieldErrors;
}

/** The branch fields — the swappable part `Dialog` wraps. */
export function BranchForm({
  code,
  name,
  locationId,
  onCodeChange,
  onNameChange,
  onLocationIdChange,
  onFieldBlur,
  errors,
}: Props) {
  const [locations, setLocations] = useState<Location[] | null>(null);
  const [locationsError, setLocationsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLocations({ limit: 100, offset: 0 })
      .then((page) => {
        if (!cancelled) setLocations(page.items);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLocationsError(error instanceof Error ? error.message : "Could not load locations.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-ds-3">
      <div className="field">
        <Label htmlFor="branch-code">Code</Label>
        <Input
          id="branch-code"
          value={code}
          onChange={(event) => onCodeChange(event.target.value)}
          onBlur={() => onFieldBlur("code")}
          autoComplete="off"
          autoFocus
          aria-invalid={errors.code !== null}
          aria-describedby={errors.code ? "branch-code-error" : undefined}
        />
        {errors.code ? (
          <p id="branch-code-error" className="hint">
            {errors.code}
          </p>
        ) : null}
      </div>

      <div className="field">
        <Label htmlFor="branch-name">Name</Label>
        <Input
          id="branch-name"
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          onBlur={() => onFieldBlur("name")}
          autoComplete="off"
          aria-invalid={errors.name !== null}
          aria-describedby={errors.name ? "branch-name-error" : undefined}
        />
        {errors.name ? (
          <p id="branch-name-error" className="hint">
            {errors.name}
          </p>
        ) : null}
      </div>

      <div className="field">
        <Label htmlFor="branch-location">Location</Label>
        <Select
          value={locationId}
          onValueChange={onLocationIdChange}
          disabled={locations === null}
          onOpenChange={(open) => !open && onFieldBlur("locationId")}
        >
          <SelectTrigger id="branch-location" className="w-full" aria-invalid={errors.locationId !== null}>
            <SelectValue placeholder={locations === null ? "Loading locations…" : "Select a location"} />
          </SelectTrigger>
          <SelectContent>
            {(locations ?? []).map((location) => (
              <SelectItem key={location.id} value={location.id}>
                {location.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {locationsError ? <p className="hint">{locationsError}</p> : null}
        {errors.locationId ? (
          <p id="branch-location-error" className="hint">
            {errors.locationId}
          </p>
        ) : null}
      </div>
    </div>
  );
}
