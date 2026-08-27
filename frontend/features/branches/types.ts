/** A branch resource, as returned by GET /branches. */
export interface Branch {
  id: string;
  code: string;
  name: string;
  location_id: string;
  active: boolean;
}
