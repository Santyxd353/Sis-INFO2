export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export const normalizeCollection = <T>(data: T[] | { results: T[] }): T[] =>
  Array.isArray(data) ? data : data.results

