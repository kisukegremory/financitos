import { authHeaders, request as base } from '../../lib/api.js'

const request = (method, path, body) => base(method, `/medichan${path}`, body)

export const api = {
  voices: () => request('GET', '/voices'),
  create: (feeling, voice) => request('POST', '/meditations', { feeling, voice }),
  list: () => request('GET', '/meditations'),
  remove: (id) => request('DELETE', `/meditations/${id}`),
  musicCatalog: () => request('GET', '/music/catalog'),
  tracks: () => request('GET', '/music'),
  compose: (body) => request('POST', '/music', body),
  removeTrack: (id) => request('DELETE', `/music/${id}`),
  publish: (id, body) => request('POST', `/meditations/${id}/publish`, body),
  published: () => request('GET', '/published'),
  unpublish: (slug) => request('DELETE', `/published/${slug}`),
  profile: () => request('GET', '/profile'),
  saveProfile: (body) => request('PUT', '/profile', body),
}

// exemplos estáticos em web/public/medichan/samples (gerados por `home medichan sample`)
export const samples = {
  list: () => fetch('/medichan/samples/index.json').then((r) => (r.ok ? r.json() : [])),
  get: (slug) => fetch(`/medichan/samples/${slug}/meditation.json`).then((r) => r.json()),
}

// áudio de fala: a rota da API pode exigir token, então baixa com fetch em vez de <audio src>
export async function loadAudio(url) {
  const res = await fetch(url, { headers: url.startsWith('/api') ? authHeaders() : {} })
  if (!res.ok) throw new Error(`áudio indisponível (${res.status})`)
  return res.arrayBuffer()
}

// URL tocável num <audio> (a rota pode exigir token, então vira blob local)
export async function audioURL(url, type = 'audio/mpeg') {
  return URL.createObjectURL(new Blob([await loadAudio(url)], { type }))
}
