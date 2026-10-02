import { query, request as base } from '../../lib/api.js'

const request = (method, path, body) => base(method, `/tarot${path}`, body)

export const api = {
  phrases: (params = {}) => request('GET', `/phrases?${query(params)}`),
  createPhrase: (phrase) => request('POST', '/phrases', phrase),
  updatePhrase: (id, changes) => request('PUT', `/phrases/${id}`, changes),
  removePhrase: (id) => request('DELETE', `/phrases/${id}`),
  generate: (body) => request('POST', '/phrases/generate', body),
  recommendThinkers: (topic) => request('POST', '/thinkers/recommend', { topic: topic || null }),
  basePrompt: () => request('GET', '/settings/base-prompt'),
  setBasePrompt: (value) => request('PUT', '/settings/base-prompt', { value }),
  draw: () => request('GET', '/cards/draw'),
  read: (feeling) => request('POST', '/readings', { feeling }),
  readings: () => request('GET', '/readings'),
  removeReading: (id) => request('DELETE', `/readings/${id}`),
}
