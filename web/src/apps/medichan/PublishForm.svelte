<script>
  // Estúdio → catálogo: renderiza o áudio final (voz + pausas + trilha) e publica.
  import { api } from './api.js'

  let { meditation, tracks = [], published = [], ondone, oncancel } = $props()

  // svelte-ignore state_referenced_locally (valor inicial é o pretendido: o pai recria o componente)
  const prev = published.find((p) => p.meditation_id === meditation.id)
  // svelte-ignore state_referenced_locally
  let title = $state(prev?.title ?? meditation.title)
  let slug = $state(prev?.slug ?? '')
  let summary = $state(prev?.summary ?? '')
  let tags = $state(prev?.tags.join(', ') ?? '')
  let access = $state(prev?.access ?? 'free')
  let track = $state(prev?.track_id ? String(prev.track_id) : '')
  let busy = $state(false)
  let error = $state('')

  async function submit(e) {
    e.preventDefault()
    busy = true
    error = ''
    try {
      const item = await api.publish(meditation.id, {
        title,
        slug: slug.trim() || null,
        summary,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        access,
        track_id: track ? Number(track) : null,
      })
      ondone(item)
    } catch (err) {
      error = err.message
    } finally {
      busy = false
    }
  }
</script>

<form class="publish" onsubmit={submit}>
  <label>Título <input bind:value={title} maxlength="120" /></label>
  <label>Slug <input bind:value={slug} placeholder="gerado do título" pattern="[a-z0-9]+(-[a-z0-9]+)*" /></label>
  <label>Resumo <input bind:value={summary} maxlength="300" /></label>
  <label>Tags <input bind:value={tags} placeholder="ansiedade, semana" /></label>
  <label>
    Acesso
    <select bind:value={access}>
      <option value="free">aberta</option>
      <option value="private">privada</option>
    </select>
  </label>
  <label>
    Trilha
    <select bind:value={track}>
      <option value="">só voz</option>
      {#each tracks as t (t.id)}<option value={String(t.id)}>{t.title}</option>{/each}
    </select>
  </label>
  {#if error}<p class="error">{error}</p>{/if}
  <div class="row">
    <button type="submit" disabled={busy}>{busy ? 'renderizando…' : prev ? 'Republicar' : 'Publicar'}</button>
    <button type="button" class="ghost" onclick={oncancel}>cancelar</button>
  </div>
</form>

<style>
  .publish { display: grid; gap: 0.5rem; padding: 0.9rem 1rem; background: var(--panel); border: 1px solid var(--border); border-radius: 18px; backdrop-filter: blur(14px); }
  .error { color: var(--danger); margin: 0; }
</style>
