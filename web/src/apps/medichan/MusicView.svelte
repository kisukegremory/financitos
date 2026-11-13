<script>
  import { onDestroy } from 'svelte'
  import { dateBR, usd } from '../../lib/format.js'
  import { api, audioURL } from './api.js'
  import { stopPreview } from './preview.svelte.js'

  let { tracks = $bindable() } = $props()

  let catalog = $state(null)
  let preset = $state('chuva')
  let extra = $state('')
  let title = $state('')
  let kind = $state('clip')
  let sending = $state(false)
  let error = $state('')

  // player da biblioteca: uma música por vez, em loop
  let audio = null
  let playingId = $state(null)
  let loadingId = $state(null)
  let progress = $state(0)

  api.musicCatalog().then((c) => (catalog = c))

  let pending = $derived(tracks.some((t) => t.status === 'pending'))
  let spent = $derived(tracks.reduce((sum, t) => sum + (t.cost_usd ?? 0), 0))

  // enquanto algo compõe, atualiza a lista a cada 5 s
  let poll = null
  $effect(() => {
    if (pending && !poll) {
      poll = setInterval(async () => (tracks = await api.tracks()), 5000)
    } else if (!pending && poll) {
      clearInterval(poll)
      poll = null
    }
  })

  async function compose() {
    error = ''
    sending = true
    try {
      const track = await api.compose({ kind, preset: preset || null, extra: extra || null, title: title || null })
      tracks = [track, ...tracks]
      extra = ''
      title = ''
    } catch (e) {
      error = e.message
    } finally {
      sending = false
    }
  }

  async function toggle(track) {
    stopPreview()
    if (playingId === track.id) return stop()
    stop()
    loadingId = track.id
    try {
      audio = new Audio(await audioURL(track.audio))
      audio.loop = true
      audio.ontimeupdate = () => (progress = audio.duration ? audio.currentTime / audio.duration : 0)
      await audio.play()
      playingId = track.id
    } catch (e) {
      error = e.message
    } finally {
      loadingId = null
    }
  }

  function stop() {
    if (audio) {
      audio.pause()
      URL.revokeObjectURL(audio.src)
    }
    audio = null
    playingId = null
    progress = 0
  }

  async function remove(track) {
    if (!confirm(`Apagar “${track.title}”?`)) return
    if (playingId === track.id) stop()
    await api.removeTrack(track.id)
    tracks = tracks.filter((t) => t.id !== track.id)
  }

  onDestroy(() => {
    stop()
    clearInterval(poll)
  })

  const clock = (s) => (s == null ? '' : `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`)
</script>

<section>
  <h2>Compor música ambiente</h2>
  <p class="muted small">
    Gerada pelo Lyria 3 (Google): instrumental, sem bateria nem voz. Dá para ouvir aqui em loop ou
    usar como trilha de fundo das meditações.
  </p>

  {#if catalog}
    <div class="chips">
      {#each catalog.presets as p (p.id)}
        <button class="ghost chip" class:active={preset === p.id} title={p.detail}
          onclick={() => (preset = preset === p.id ? '' : p.id)}>{p.label}</button>
      {/each}
    </div>

    <label>
      descrição extra (opcional · em inglês o Lyria entende melhor)
      <input bind:value={extra} placeholder="ex.: with distant thunder, very soft cello" maxlength="500" />
    </label>

    <div class="row options">
      <label class="grow">
        nome (opcional)
        <input bind:value={title} placeholder={catalog.presets.find((p) => p.id === preset)?.label ?? 'minha trilha'} maxlength="80" />
      </label>
      {#each catalog.lengths as l (l.id)}
        <label class="length" class:active={kind === l.id}>
          <input type="radio" bind:group={kind} value={l.id} />
          <span><strong>{l.label}</strong><br /><span class="muted">{l.detail}</span></span>
        </label>
      {/each}
    </div>

    <button class="go" disabled={sending || (!preset && !extra.trim())} onclick={compose}>
      {sending ? 'enviando…' : `🎶 compor · ${usd(catalog.prices[kind])}`}
    </button>
    {#if error}<p class="error">{error}</p>{/if}
  {/if}
</section>

<section>
  <div class="row spread">
    <h2>Biblioteca</h2>
    {#if tracks.length}<span class="muted small">{tracks.length} músicas · {usd(spent)} gastos</span>{/if}
  </div>
  {#if !tracks.length}<p class="muted">Nenhuma música ainda.</p>{/if}

  <div class="list">
    {#each tracks as t (t.id)}
      <div class="track" class:playing={playingId === t.id}>
        {#if t.status === 'ready'}
          <button class="ghost play" onclick={() => toggle(t)} disabled={loadingId === t.id}>
            {loadingId === t.id ? '…' : playingId === t.id ? '■' : '▶'}
          </button>
        {:else if t.status === 'pending'}
          <span class="play spinner" title="compondo">◌</span>
        {:else}
          <span class="play" title={t.error}>⚠</span>
        {/if}
        <div class="info">
          <strong>{t.title}</strong>
          <span class="muted small">
            {t.kind === 'pro' ? 'peça completa' : 'clip'}
            {#if t.seconds} · {clock(t.seconds)}{/if}
            {#if t.cost_usd != null} · {usd(t.cost_usd)}{/if}
            · {dateBR(t.created_at.slice(0, 10))}
          </span>
          {#if t.status === 'pending'}
            <span class="muted small">compondo… ({t.kind === 'pro' ? '~2,5 min' : '~10 s'})</span>
          {:else if t.status === 'error'}
            <span class="error small">{t.error}</span>
          {/if}
          {#if playingId === t.id}
            <div class="bar"><div style:width="{progress * 100}%"></div></div>
          {/if}
        </div>
        <button class="ghost del" title="apagar" onclick={() => remove(t)}>✕</button>
      </div>
    {/each}
  </div>
</section>

<style>
  .small { font-size: 0.8rem; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.75rem 0; }
  .chip { font-size: 0.85rem; padding: 0.35rem 0.9rem !important; border-radius: 999px; }
  .chip.active { border-color: var(--accent) !important; color: var(--accent) !important; background: rgba(232, 207, 154, 0.12) !important; }
  label input { width: 100%; box-sizing: border-box; }
  .options { margin: 0.75rem 0; align-items: stretch; }
  .grow { flex: 1; min-width: 180px; }
  .length {
    background: rgba(10, 10, 26, 0.3);
    flex-direction: row; align-items: center; gap: 0.5rem; cursor: pointer;
    border: 1px solid var(--border); border-radius: 14px; padding: 0.5rem 0.8rem;
  }
  .length.active { border-color: var(--accent); }
  .length input { width: auto; }
  .length strong { color: var(--text); font-weight: 500; }
  .go { width: 100%; padding: 0.9rem !important; }
  .error { color: var(--danger); }

  .list { display: grid; gap: 0.5rem; }
  .track {
    display: flex; align-items: center; gap: 0.75rem;
    border: 1px solid var(--border); border-radius: 16px; padding: 0.6rem 0.75rem;
    background: rgba(10, 10, 26, 0.3);
  }
  .track.playing { border-color: var(--accent); }
  .play { width: 2.6rem; height: 2.6rem; text-align: center; padding: 0 !important; flex: none; }
  .info strong { font-family: var(--serif); font-size: 1.15rem; font-weight: 500; }
  .spinner { display: inline-block; animation: spin 2s linear infinite; color: var(--accent); }
  @keyframes spin { to { transform: rotate(360deg); } }
  .info { flex: 1; display: flex; flex-direction: column; gap: 0.15rem; }
  .bar { height: 2px; background: var(--border); margin-top: 0.3rem; }
  .bar div { height: 100%; background: var(--accent); }
</style>
