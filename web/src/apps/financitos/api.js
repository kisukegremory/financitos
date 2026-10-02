import { query, request as base } from '../../lib/api.js'

const request = (method, path, body) => base(method, `/financitos${path}`, body)

export const api = {
  categories: () => request('GET', '/categories'),
  parse: (text, source, invoice) => request('POST', '/parse', { text, source, invoice }),
  saveBulk: (items) => request('POST', '/transactions/bulk', items),
  list: (params) => request('GET', `/transactions?${query(params)}`),
  update: (id, changes) => request('PUT', `/transactions/${id}`, changes),
  remove: (id) => request('DELETE', `/transactions/${id}`),
  pay: (invoice, source, paid_at) =>
    request('POST', `/invoices/${invoice}/pay`, { source, paid_at: paid_at || null }),
  payments: (params) => request('GET', `/payments?${query(params)}`),
  removePayment: (id) => request('DELETE', `/payments/${id}`),
  balances: () => request('GET', '/balances'),
  setBalance: (category, amount) =>
    request('PUT', `/balances/${encodeURIComponent(category)}`, { amount }),
  summary: (invoice, source) => request('GET', `/invoices/${invoice}/summary?${query({ source })}`),
}
