/** The shape every paged list endpoint returns (limit/offset, per the API's own convention). */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
