interface Props {
  name: string;
  onNameChange: (value: string) => void;
  onNameBlur: () => void;
  /** Only shown once the field has been touched, so the popup doesn't open already complaining. */
  error: string | null;
}

/** Just the Name field — the swappable part `Dialog` wraps. */
export function LocationForm({ name, onNameChange, onNameBlur, error }: Props) {
  return (
    <div className="field">
      <label htmlFor="location-name">Name</label>
      <input
        id="location-name"
        className="input"
        value={name}
        onChange={(event) => onNameChange(event.target.value)}
        onBlur={onNameBlur}
        autoComplete="off"
        autoFocus
        aria-invalid={error !== null}
        aria-describedby={error ? "location-name-error" : undefined}
      />
      {error ? (
        <p id="location-name-error" className="hint">
          {error}
        </p>
      ) : null}
    </div>
  );
}
