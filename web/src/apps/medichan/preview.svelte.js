// Toca uma amostra de voz por vez (arquivos estáticos em /medichan/voices)
let audio = null

export const preview = $state({ id: null, error: null })

export function togglePreview(voice) {
  audio?.pause()
  if (preview.id === voice.id) {
    preview.id = null
    return
  }
  audio = new Audio(voice.preview)
  preview.id = voice.id
  preview.error = null
  audio.onended = () => (preview.id = null)
  audio.play().catch(() => {
    preview.error = voice.id // amostra ainda não gerada (home medichan voices)
    preview.id = null
  })
}

export function stopPreview() {
  audio?.pause()
  preview.id = null
}
