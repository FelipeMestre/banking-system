interface FieldErrors {
  identificationNumber: string | null;
  firstName: string | null;
  lastName: string | null;
  dateOfBirth: string | null;
}

interface Props {
  identificationNumber: string;
  firstName: string;
  lastName: string;
  dateOfBirth: string;
  gender: string;
  onIdentificationNumberChange: (value: string) => void;
  onFirstNameChange: (value: string) => void;
  onLastNameChange: (value: string) => void;
  onDateOfBirthChange: (value: string) => void;
  onGenderChange: (value: string) => void;
  onFieldBlur: (field: keyof FieldErrors) => void;
  /** Only shown once a field has been touched, so the popup doesn't open already complaining. */
  errors: FieldErrors;
}

/** The customer fields — the swappable part `Dialog` wraps. */
export function CustomerForm({
  identificationNumber,
  firstName,
  lastName,
  dateOfBirth,
  gender,
  onIdentificationNumberChange,
  onFirstNameChange,
  onLastNameChange,
  onDateOfBirthChange,
  onGenderChange,
  onFieldBlur,
  errors,
}: Props) {
  return (
    <div className="flex flex-col gap-ds-3">
      <div className="field">
        <label htmlFor="customer-identification-number">Identification Number</label>
        <input
          id="customer-identification-number"
          className="input"
          value={identificationNumber}
          onChange={(event) => onIdentificationNumberChange(event.target.value)}
          onBlur={() => onFieldBlur("identificationNumber")}
          autoComplete="off"
          autoFocus
          aria-invalid={errors.identificationNumber !== null}
          aria-describedby={errors.identificationNumber ? "customer-identification-number-error" : undefined}
        />
        {errors.identificationNumber ? (
          <p id="customer-identification-number-error" className="hint">
            {errors.identificationNumber}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="customer-first-name">First Name</label>
        <input
          id="customer-first-name"
          className="input"
          value={firstName}
          onChange={(event) => onFirstNameChange(event.target.value)}
          onBlur={() => onFieldBlur("firstName")}
          autoComplete="off"
          aria-invalid={errors.firstName !== null}
          aria-describedby={errors.firstName ? "customer-first-name-error" : undefined}
        />
        {errors.firstName ? (
          <p id="customer-first-name-error" className="hint">
            {errors.firstName}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="customer-last-name">Last Name</label>
        <input
          id="customer-last-name"
          className="input"
          value={lastName}
          onChange={(event) => onLastNameChange(event.target.value)}
          onBlur={() => onFieldBlur("lastName")}
          autoComplete="off"
          aria-invalid={errors.lastName !== null}
          aria-describedby={errors.lastName ? "customer-last-name-error" : undefined}
        />
        {errors.lastName ? (
          <p id="customer-last-name-error" className="hint">
            {errors.lastName}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="customer-date-of-birth">Date of Birth</label>
        <input
          id="customer-date-of-birth"
          type="date"
          className="input"
          value={dateOfBirth}
          onChange={(event) => onDateOfBirthChange(event.target.value)}
          onBlur={() => onFieldBlur("dateOfBirth")}
          aria-invalid={errors.dateOfBirth !== null}
          aria-describedby={errors.dateOfBirth ? "customer-date-of-birth-error" : undefined}
        />
        {errors.dateOfBirth ? (
          <p id="customer-date-of-birth-error" className="hint">
            {errors.dateOfBirth}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="customer-gender">Gender (optional)</label>
        <select
          id="customer-gender"
          className="input"
          value={gender}
          onChange={(event) => onGenderChange(event.target.value)}
        >
          <option value="">Prefer not to say</option>
          <option value="Female">Female</option>
          <option value="Male">Male</option>
          <option value="Other">Other</option>
        </select>
      </div>
    </div>
  );
}
