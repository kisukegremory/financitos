const TOKEN_KEY = 'financitos:token'

async function request(method, path, body) {
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

export const api = {
  categories: () => request('GET', '/categories'),
  parse: (text, source, invoice) => request('POST', '/parse', { text, source, invoice }),
  saveBulk: (items) => request('POST', '/transactions/bulk', items),
  list: (params) => request('GET', `/transactions?${new URLSearchParams(clean(params))}`),
  update: (id, changes) => request('PUT', `/transactions/${id}`, changes),
  remove: (id) => request('DELETE', `/transactions/${id}`),
  pay: (invoice, source, paid_at) =>
    request('POST', `/invoices/${invoice}/pay`, { source, paid_at: paid_at || null }),
  payments: (params) => request('GET', `/payments?${new URLSearchParams(clean(params))}`),
  removePayment: (id) => request('DELETE', `/payments/${id}`),
  summary: (invoice, source) =>
    request('GET', `/invoices/${invoice}/summary?${new URLSearchParams(clean({ source }))}`),
}

function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v))
}
