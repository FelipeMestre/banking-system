/** A customer resource, as returned by GET /customers. */
export interface Customer {
  id: string;
  identification_number: string;
  first_name: string;
  last_name: string;
  /** ISO 8601 date. Personal data — display only, never log (spec §3.4). */
  date_of_birth: string;
  gender: string | null;
  /** Derived server-side from date_of_birth on every read. */
  age: number;
  active: boolean;
}
