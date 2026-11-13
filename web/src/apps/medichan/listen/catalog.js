// Consumo: a única fonte é o catalog.json publicado pelo estúdio (contrato em
// docs/medichan-catalog.md). Os caminhos dos áudios são relativos ao catálogo, então
// trocar BASE por um bucket/CDN basta para o site/app externo.
import { audioURL } from '../api.js'

export const BASE = '/api/medichan/public/'

export async function loadCatalog() {
  const res = await fetch(`${BASE}catalog.json`)
  if (!res.ok) throw new Error(`catálogo indisponível (${res.status})`)
  return res.json()
}

const resolve = (path) => new URL(path, new URL(BASE, location.href)).href

// livre: URL direta (streaming com Range); privado: precisa do token, vira blob local
export async function sources(item) {
  if (item.access === 'free') {
    return [
      { src: resolve(item.audio.ogg), type: 'audio/ogg; codecs=opus' },
      { src: resolve(item.audio.m4a), type: 'audio/mp4' },
    ]
  }
  const url = resolve(item.audio.m4a).replace(location.origin, '')
  return [{ src: await audioURL(url, 'audio/mp4'), type: 'audio/mp4' }]
}

export function duration(s) {
  const m = Math.round(s / 60)
  return m < 1 ? '< 1 min' : `${m} min`
}
