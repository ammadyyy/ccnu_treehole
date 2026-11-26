// 统一 API 封装：同源相对路径 /api/*，携带 httpOnly 会话 Cookie。

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string }
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let code = 'UNKNOWN'
    let message = res.statusText
    try {
      const data = (await res.json()) as ErrorBody
      if (data.error) {
        code = data.error.code ?? code
        message = data.error.message ?? message
      }
    } catch {
      // 非 JSON 响应，保留默认信息
    }
    throw new ApiError(res.status, code, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  return parseResponse<T>(res)
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  // multipart 不手动设 Content-Type，由浏览器自动带 boundary
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData,
  })
  return parseResponse<T>(res)
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) => upload<T>(path, formData),
}
