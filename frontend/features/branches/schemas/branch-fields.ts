/** Validates a branch's code; returns an error message, or null if valid. */
export function validateBranchCode(value: string): string | null {
  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return "Code is required.";
  }
  if (trimmed.length > 10) {
    return "Code cannot be longer than 10 characters.";
  }
  if (!/^[A-Za-z0-9]+$/.test(trimmed)) {
    return "Code can only contain letters and digits.";
  }
  return null;
}

/** Validates a branch's name; returns an error message, or null if valid. */
export function validateBranchName(value: string): string | null {
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

/** Validates a branch's location selection; returns an error message, or null if valid. */
export function validateBranchLocationId(value: string): string | null {
  if (value.trim().length === 0) {
    return "A location is required.";
  }
  return null;
}
