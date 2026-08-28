"use client";

import { useEffect, useState } from "react";
import { getLocations } from "@/features/locations";
import type { Location } from "@/features/locations";

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
        <label htmlFor="branch-code">Code</label>
        <input
          id="branch-code"
          className="input"
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
        <label htmlFor="branch-name">Name</label>
        <input
          id="branch-name"
          className="input"
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
        <label htmlFor="branch-location">Location</label>
        <select
          id="branch-location"
          className="input"
          value={locationId}
          onChange={(event) => onLocationIdChange(event.target.value)}
          onBlur={() => onFieldBlur("locationId")}
          disabled={locations === null}
          aria-invalid={errors.locationId !== null}
          aria-describedby={errors.locationId ? "branch-location-error" : undefined}
        >
          <option value="">{locations === null ? "Loading locations…" : "Select a location"}</option>
          {(locations ?? []).map((location) => (
            <option key={location.id} value={location.id}>
              {location.name}
            </option>
          ))}
        </select>
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
