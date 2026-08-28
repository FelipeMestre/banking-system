import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Radix Select doesn't allow an item with an empty-string value (that's
// reserved to mean "nothing selected") — this sentinel stands in for the
// gender field's own "no answer" state, translated back to "" at the edges.
const UNSPECIFIED_GENDER = "unspecified";

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
        <Label htmlFor="customer-identification-number">Identification Number</Label>
        <Input
          id="customer-identification-number"
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
        <Label htmlFor="customer-first-name">First Name</Label>
        <Input
          id="customer-first-name"
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
        <Label htmlFor="customer-last-name">Last Name</Label>
        <Input
          id="customer-last-name"
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
        <Label htmlFor="customer-date-of-birth">Date of Birth</Label>
        <Input
          id="customer-date-of-birth"
          type="date"
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
        <Label htmlFor="customer-gender">Gender (optional)</Label>
        <Select
          value={gender === "" ? UNSPECIFIED_GENDER : gender}
          onValueChange={(value) => onGenderChange(value === UNSPECIFIED_GENDER ? "" : value)}
        >
          <SelectTrigger id="customer-gender" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={UNSPECIFIED_GENDER}>Prefer not to say</SelectItem>
            <SelectItem value="Female">Female</SelectItem>
            <SelectItem value="Male">Male</SelectItem>
            <SelectItem value="Other">Other</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
