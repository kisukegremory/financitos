<script>
  import { dateBR, usd } from '../../lib/format.js'
  import { link } from '../../lib/router.svelte.js'
  import { api, samples } from './api.js'
  import CreateView from './CreateView.svelte'
  import MusicView from './MusicView.svelte'
  import Player from './Player.svelte'
  import { stopPreview } from './preview.svelte.js'
  import VoicesView from './VoicesView.svelte'

  let tab = $state('create')
  let playing = $state(null)
  let mine = $state([])
  let examples = $state([])
  let voices = $state([])
  let voice = $state('gemini')
  let tracks = $state([])

  api.list().then((m) => (mine = m))
  api.voices().then((v) => (voices = v))
  samples.list().then((s) => (examples = s))
  api.tracks().then((t) => (tracks = t))

  // "Gemini 3.8 Flash · Sulafat"; ids antigos/desconhecidos aparecem crus
  const voiceName = (id) => {
    const v = voices.find((x) => x.id === id)
    return v ? `${v.provider} · ${v.label}` : id
  }

  function go(next) {
    stopPreview()
    tab = next
  }

  function play(m) {
    stopPreview()
    playing = m
  }

  function ready(m) {
    mine = [m, ...mine]
    play(m)
  }

  async function openSample(slug) {
    play(await samples.get(slug))
  }

  async function remove(m) {
    if (!confirm('Apagar esta meditação?')) return
    await api.remove(m.id)
    mine = mine.filter((x) => x.id !== m.id)
  }

  let spent = $derived(mine.reduce((sum, m) => sum + (m.cost_usd ?? 0), 0))
</script>

<div class="medichan">
  <header>
    <h1><a href="/" onclick={link} class="home-link">⌂</a> 🪷 medichan</h1>
    {#if !playing}
      <nav>
        <button class:active={tab === 'create'} onclick={() => go('create')}>Criar</button>
        <button class:active={tab === 'mine'} onclick={() => go('mine')}>Minhas</button>
        <button class:active={tab === 'voices'} onclick={() => go('voices')}>Vozes</button>
        <button class:active={tab === 'music'} onclick={() => go('music')}>Músicas</button>
        <button class:active={tab === 'samples'} onclick={() => go('samples')}>Exemplos</button>
      </nav>
    {/if}
  </header>

  <main>
    {#if playing}
      {#key playing}
        <Player
          meditation={playing}
          voiceName={voiceName(playing.voice)}
          tracks={tracks.filter((t) => t.status === 'ready')}
          onclose={() => (playing = null)}
        />
      {/key}
    {:else if tab === 'create'}
      <CreateView {voices} bind:voice onready={ready} />
    {:else if tab === 'music'}
      <MusicView bind:tracks />
    {:else if tab === 'voices'}
      <VoicesView {voices} onpick={(id) => ((voice = id), go('create'))} />
    {:else}
      {@const items = tab === 'mine' ? mine : examples}
      {#if tab === 'mine' && mine.length}
        <p class="muted small total">
          {mine.length} meditações · {usd(spent)} gastos em voz
        </p>
      {/if}
      {#if !items.length}
        <p class="muted">
          {tab === 'mine' ? 'Nenhuma meditação ainda. Crie a primeira em “Criar”.' : 'Nenhum exemplo gerado.'}
        </p>
      {/if}
      <div class="list">
        {#each items as m (m.id ?? m.slug)}
          <div class="item">
            <button class="ghost open" onclick={() => (m.slug ? openSample(m.slug) : play(m))}>
              <strong>{m.title}</strong>
              <span class="muted">“{m.feeling}”</span>
              <span class="muted small">
                🎙 {voiceName(m.voice)}
                {#if m.cost_usd != null} · {usd(m.cost_usd)}{/if}
                {#if m.created_at} · {dateBR(m.created_at.slice(0, 10))}{/if}
              </span>
            </button>
            {#if m.id}<button class="ghost del" title="apagar" onclick={() => remove(m)}>✕</button>{/if}
          </div>
        {/each}
      </div>
    {/if}
  </main>
</div>

<style>
  /* tom calmo só dentro do medichan */
  .medichan { --accent: #6fd3c1; }
  .list { display: grid; gap: 0.6rem; }
  .item { display: flex; gap: 0.4rem; }
  .open {
    flex: 1; display: flex; flex-direction: column; align-items: flex-start; gap: 0.25rem;
    text-align: left; padding: 0.9rem 1rem; background: var(--panel); border-radius: 10px;
  }
  .open:hover { border-color: var(--accent); }
  .del { align-self: stretch; }
  .small { font-size: 0.8rem; }
  .total { margin-top: 0; }
</style>
