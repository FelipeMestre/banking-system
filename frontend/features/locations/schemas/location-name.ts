/** Validates a location's name; returns an error message, or null if valid. */
export function validateLocationName(value: string): string | null {
  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return "Name is required.";
  }
  if (/^\d+$/.test(trimmed)) {
    return "Name cannot be only numbers.";
  }
  if (!/^\p{Lu}/u.test(trimmed)) {
    return "Name must start with an uppercase letter.";
  }
  return null;
}
