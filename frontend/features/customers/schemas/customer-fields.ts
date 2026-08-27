/** Validates a person's first/last name; returns an error message, or null if valid. */
export function validatePersonName(value: string, label: string): string | null {
  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return `${label} is required.`;
  }
  if (/^\d+$/.test(trimmed)) {
    return `${label} cannot be only numbers.`;
  }
  if (!/^\p{Lu}/u.test(trimmed)) {
    return `${label} must start with an uppercase letter.`;
  }
  return null;
}

/** Validates a customer's identification number; returns an error message, or null if valid. */
export function validateIdentificationNumber(value: string): string | null {
  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return "Identification number is required.";
  }
  if (trimmed.length > 20) {
    return "Identification number cannot be longer than 20 characters.";
  }
  if (!/^[A-Za-z0-9.-]+$/.test(trimmed)) {
    return "Identification number can only contain letters, digits, dots, and hyphens.";
  }
  return null;
}

/** Validates a customer's date of birth; returns an error message, or null if valid. */
export function validateDateOfBirth(value: string): string | null {
  if (value.trim().length === 0) {
    return "Date of birth is required.";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Date of birth is not a valid date.";
  }
  if (parsed.getTime() > Date.now()) {
    return "Date of birth cannot be in the future.";
  }
  return null;
}
