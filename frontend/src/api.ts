export class ApiError extends Error {
  constructor(
    message: string,
    public code = '',
    public status = 0,
  ) {
    super(message)
  }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    let code = ''
    try {
      const body = await response.json()
      message =
        typeof body.detail === 'string'
          ? body.detail
          : body.detail?.message || JSON.stringify(body.detail)
      code = body.detail?.code || ''
    } catch {
      /* Keep HTTP status when the response is not JSON. */
    }
    throw new ApiError(message, code, response.status)
  }
  return response.json() as Promise<T>
}
