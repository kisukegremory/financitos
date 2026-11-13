// Botões do fone/tela de bloqueio (Media Session) para quem toca via Web Audio.
// O navegador só entrega esses eventos a páginas com um <audio> tocando; por isso um WAV
// silencioso fica em loop enquanto a meditação toca e acompanha play/pause.

function silentWav(seconds = 2, rate = 8000) {
  const n = seconds * rate
  const buf = new ArrayBuffer(44 + n)
  const v = new DataView(buf)
  const str = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)))
  str(0, 'RIFF'); v.setUint32(4, 36 + n, true); str(8, 'WAVEfmt ')
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
  v.setUint32(24, rate, true); v.setUint32(28, rate, true); v.setUint16(32, 1, true)
  v.setUint16(34, 8, true); str(36, 'data'); v.setUint32(40, n, true)
  new Uint8Array(buf, 44).fill(128) // 8 bits sem sinal: 128 = silêncio
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }))
}

/** Liga os controles de mídia; `onplay`/`onpause` são chamados pelos botões do fone. */
export function createMediaSession({ title, artist = 'medichan', artwork, onplay, onpause }) {
  const url = silentWav()
  const keepalive = new Audio(url)
  keepalive.loop = true
  const ms = 'mediaSession' in navigator ? navigator.mediaSession : null

  if (ms) {
    ms.metadata = new MediaMetadata({
      title, artist, artwork: artwork ? [{ src: artwork, sizes: '512x512', type: 'image/webp' }] : [],
    })
    ms.setActionHandler('play', () => onplay())
    ms.setActionHandler('pause', () => onpause())
    ms.setActionHandler('stop', () => onpause())
  }
  // outro app tomou o áudio (ligação, etc.) e pausou o elemento: pausa a meditação junto
  let silencing = false
  keepalive.onpause = () => { if (!silencing) onpause() }

  return {
    playing() {
      keepalive.play().catch(() => {})
      if (ms) ms.playbackState = 'playing'
    },
    paused() {
      silencing = true
      keepalive.pause()
      silencing = false
      if (ms) ms.playbackState = 'paused'
    },
    destroy() {
      silencing = true
      keepalive.pause()
      URL.revokeObjectURL(url)
      if (ms) {
        for (const a of ['play', 'pause', 'stop']) ms.setActionHandler(a, null)
        ms.playbackState = 'none'
      }
    },
  }
}
