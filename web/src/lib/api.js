const TOKEN_KEY = 'home:token'

export async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (res.status === 401) {
    const t = prompt('Token da API:')
    if (t) {
      localStorage.setItem(TOKEN_KEY, t)
      return request(method, path, body)
    }
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(typeof detail.detail === 'string' ? detail.detail : `${res.status} ${res.statusText}`)
  }
  return res.status === 204 ? null : res.json()
}

export function query(params) {
  return new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v)))
}
