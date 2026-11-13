<script>
  import { dateBR, usd } from '../../lib/format.js'
  import { link } from '../../lib/router.svelte.js'
  import { api, samples } from './api.js'
  import AboutView from './AboutView.svelte'
  import CreateView from './CreateView.svelte'
  import Listen from './listen/Listen.svelte'
  import MusicView from './MusicView.svelte'
  import Player from './Player.svelte'
  import PublishForm from './PublishForm.svelte'
  import { stopPreview } from './preview.svelte.js'
  import VoicesView from './VoicesView.svelte'

  let tab = $state('create')
  let playing = $state(null)
  let mine = $state([])
  let examples = $state([])
  let voices = $state([])
  let voice = $state('gemini')
  let tracks = $state([])
  let published = $state([])
  let publishing = $state(null) // id da meditação com o formulário aberto

  api.list().then((m) => (mine = m))
  api.voices().then((v) => (voices = v))
  samples.list().then((s) => (examples = s))
  api.tracks().then((t) => (tracks = t))
  api.published().then((p) => (published = p))

  function didPublish(item) {
    published = [item, ...published.filter((p) => p.slug !== item.slug)]
    publishing = null
  }

  const publishedOf = (m) => published.find((p) => p.meditation_id === m.id)

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

  // abas: ícone + rótulo; no celular viram a barra inferior
  const TABS = [
    { id: 'listen', icon: '☾', label: 'Ouvir' },
    { id: 'create', icon: '✿', label: 'Criar' },
    { id: 'mine', icon: '◌', label: 'Minhas' },
    { id: 'music', icon: '♫', label: 'Sons' },
    { id: 'voices', icon: '◠', label: 'Vozes' },
    { id: 'about', icon: '♡', label: 'Sobre mim' },
  ]
  const ART = { create: 'create', music: 'music' }
  let art = $derived(playing ? 'player' : (ART[tab] ?? 'hero'))

  const hour = new Date().getHours()
  const greeting = hour < 5 ? 'Boa noite' : hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'
  const SUBTITLE = {
    listen: 'Respire. Escolha algo para ouvir.',
    create: 'Uma meditação feita para este momento.',
    mine: 'O que você já criou.',
    music: 'Paisagens sonoras para acompanhar.',
    voices: 'Encontre a voz que te acalma.',
    about: 'Conte um pouco de você.',
  }

  let spent = $derived(mine.reduce((sum, m) => sum + (m.cost_usd ?? 0), 0))
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link
    rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;1,400&family=Nunito:wght@300;400;600&display=swap"
  />
  <meta name="theme-color" content="#14152a" />
  <link rel="icon" type="image/png" href="/medichan/art/icon.png" />
</svelte:head>

<div class="medichan" class:immersive={!!playing}>
  {#each ['hero', 'create', 'music', 'player'] as a (a)}
    <div class="backdrop" class:shown={art === a} style:background-image="url(/medichan/art/{a}.webp)"></div>
  {/each}
  <div class="veil"></div>

  {#if !playing}
    <header class="bar">
      <a href="/" onclick={link} class="brand" title="home">
        <img src="/medichan/art/mascot.webp" alt="" class="logo" /><span>medichan</span>
      </a>
      <nav class="tabs">
        {#each TABS as t (t.id)}
          <button class:active={tab === t.id} onclick={() => go(t.id)}>
            <span class="icon" aria-hidden="true">{t.icon}</span><span class="label">{t.label}</span>
          </button>
        {/each}
      </nav>
    </header>

    <div class="intro">
      <div>
        <p class="hello">{greeting}</p>
        <h1>{SUBTITLE[tab]}</h1>
      </div>
      <img src="/medichan/art/mascot.webp" alt="mascote: gatinha monja meditando" class="mascot" />
    </div>
  {/if}

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
    {:else if tab === 'listen'}
      <Listen />
    {:else if tab === 'create'}
      <CreateView {voices} bind:voice onready={ready} />
    {:else if tab === 'music'}
      <MusicView bind:tracks />
    {:else if tab === 'about'}
      <AboutView />
    {:else if tab === 'voices'}
      <VoicesView {voices} onpick={(id) => ((voice = id), go('create'))} />
    {:else}
      {#if mine.length}
        <p class="muted small total">{mine.length} meditações · {usd(spent)} gastos em voz</p>
      {:else}
        <p class="muted empty">Nenhuma meditação ainda. <button class="link" onclick={() => go('create')}>Crie a primeira.</button></p>
      {/if}
      <div class="list">
        {#each mine as m (m.id)}
          <div class="item">
            <button class="open" onclick={() => play(m)}>
              <span class="dot" aria-hidden="true">▶</span>
              <span class="text">
                <strong>{m.title}</strong>
                <span class="muted feel">“{m.feeling}”</span>
                <span class="muted small">
                  {voiceName(m.voice)}
                  {#if m.cost_usd != null} · {usd(m.cost_usd)}{/if}
                  {#if m.created_at} · {dateBR(m.created_at.slice(0, 10))}{/if}
                </span>
              </span>
            </button>
            <div class="actions">
              <button
                class="ghost icon-btn"
                class:done={!!publishedOf(m)}
                title={publishedOf(m) ? `publicada: ${publishedOf(m).slug}` : 'publicar'}
                onclick={() => (publishing = publishing === m.id ? null : m.id)}
              >{publishedOf(m) ? '✓' : '⇪'}</button>
              <button class="ghost icon-btn" title="apagar" onclick={() => remove(m)}>✕</button>
            </div>
          </div>
          {#if publishing === m.id}
            <PublishForm
              meditation={m}
              tracks={tracks.filter((t) => t.status === 'ready')}
              {published}
              ondone={didPublish}
              oncancel={() => (publishing = null)}
            />
          {/if}
        {/each}
      </div>

      {#if examples.length}
        <h2 class="section-title">Exemplos</h2>
        <div class="list">
          {#each examples as m (m.slug)}
            <button class="open" onclick={() => openSample(m.slug)}>
              <span class="dot" aria-hidden="true">▶</span>
              <span class="text">
                <strong>{m.title}</strong>
                <span class="muted feel">“{m.feeling}”</span>
                <span class="muted small">{voiceName(m.voice)}</span>
              </span>
            </button>
          {/each}
        </div>
      {/if}
    {/if}
  </main>
</div>

<style>
  /* ── tema do medichan: crepúsculo, luz de lua, vidro fosco ───────────────── */
  .medichan {
    --bg: rgba(14, 15, 32, 0.55);
    --panel: rgba(28, 28, 54, 0.52);
    --border: rgba(214, 208, 255, 0.14);
    --text: #f1ece2;
    --muted: #b4b1c8;
    --accent: #e8cf9a; /* luz da lua */
    --sage: #a9c4b0;
    --danger: #f0a0a0;
    --serif: 'Cormorant Garamond', 'Iowan Old Style', Georgia, serif;
    --sans: 'Nunito', system-ui, sans-serif;
    --radius: 22px;

    position: relative; min-height: 100dvh; isolation: isolate; overflow-x: clip;
    font-family: var(--sans); font-weight: 400; color: var(--text);
    padding-bottom: calc(5.5rem + env(safe-area-inset-bottom));
  }

  /* arte de fundo (troca com fade suave entre as abas) */
  .backdrop {
    position: fixed; inset: 0; z-index: -2;
    background-size: cover; background-position: center 35%;
    opacity: 0; transform: scale(1.04);
    transition: opacity 1.6s ease, transform 12s ease-out;
  }
  .backdrop.shown { opacity: 1; transform: scale(1); }
  .veil {
    position: fixed; inset: 0; z-index: -1;
    background:
      linear-gradient(180deg, rgba(12, 12, 28, 0.15) 0%, rgba(12, 12, 28, 0.55) 45%, rgba(10, 10, 24, 0.92) 100%);
  }
  /* no player a arte vira só atmosfera: a lua desfocada não compete com o círculo */
  .immersive .backdrop.shown { filter: blur(10px) brightness(0.8); transform: scale(1.08); }
  .immersive .veil { background: radial-gradient(ellipse at center, rgba(10, 10, 24, 0.2), rgba(10, 10, 24, 0.85)); }

  /* ── cabeçalho ── */
  .bar {
    max-width: 960px; margin: 0 auto; padding: 1.1rem 1.25rem;
    display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  }
  .brand {
    display: flex; align-items: center; gap: 0.5rem;
    font-family: var(--serif); font-size: 1.6rem; letter-spacing: 0.02em;
    color: var(--text); text-decoration: none;
  }
  .tabs { display: flex; gap: 0.25rem; padding: 0.3rem; border-radius: 999px;
    background: var(--panel); border: 1px solid var(--border); backdrop-filter: blur(14px); }
  .tabs button {
    display: flex; align-items: center; gap: 0.4rem;
    background: transparent !important; border: 0; border-radius: 999px; color: var(--muted) !important;
    padding: 0.45rem 0.95rem; font-weight: 400; transition: color 0.4s, background 0.4s;
  }
  .tabs button:hover { color: var(--text) !important; }
  .tabs button.active { background: rgba(232, 207, 154, 0.16) !important; color: var(--accent) !important; }
  .tabs .icon { font-size: 1rem; line-height: 1; }

  .logo { height: 2.2rem; image-rendering: pixelated; }
  .intro {
    max-width: 960px; margin: 0 auto; padding: 3rem 1.25rem 1.5rem;
    display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
  }
  .mascot {
    width: clamp(84px, 16vw, 150px); image-rendering: pixelated; flex: none;
    filter: drop-shadow(0 0 22px rgba(232, 207, 154, 0.35));
    animation: float 7s ease-in-out infinite;
  }
  @keyframes float { 50% { transform: translateY(-6px); } }
  @media (prefers-reduced-motion: reduce) {
    .mascot { animation: none; }
    .backdrop { transition: opacity 0.4s; transform: none; }
  }
  .hello { margin: 0; color: var(--sage); letter-spacing: 0.18em; text-transform: uppercase; font-size: 0.75rem; }
  h1 {
    font-family: var(--serif); font-weight: 400; font-size: clamp(2rem, 5.5vw, 3.2rem);
    line-height: 1.1; margin: 0.4rem 0 0; text-shadow: 0 2px 30px rgba(0, 0, 0, 0.4);
  }
  main { max-width: 960px; margin: 0 auto; padding: 0 1.25rem 2rem; min-width: 0; }
  .medichan :global(:is(select, input)) { max-width: 100%; }
  .immersive main { max-width: 760px; }

  /* ── celular: abas viram barra inferior ── */
  @media (max-width: 720px) {
    .bar { padding: 0.9rem 1rem; }
    .tabs {
      position: fixed; z-index: 10; left: 0.75rem; right: 0.75rem;
      bottom: calc(0.75rem + env(safe-area-inset-bottom));
      justify-content: space-around; border-radius: 26px; padding: 0.35rem;
      background: rgba(20, 20, 42, 0.78); backdrop-filter: blur(18px);
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    }
    .tabs button { flex-direction: column; gap: 0.15rem; padding: 0.45rem 0.4rem; flex: 1; min-width: 0; border-radius: 20px; font-size: 0.68rem; white-space: nowrap; }
    .tabs .icon { font-size: 1.25rem; }
    .intro { padding: 1.75rem 1rem 1rem; }
    main { padding: 0 0.85rem 1.5rem; }
  }

  /* ── componentes compartilhados das abas (filhos também usam) ── */
  .medichan :global(h2) { font-family: var(--serif); font-weight: 500; font-size: 1.6rem; margin: 0 0 0.5rem; }
  .medichan :global(section) {
    background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius);
    padding: clamp(1.1rem, 3vw, 1.75rem); margin-bottom: 1.25rem;
    backdrop-filter: blur(18px) saturate(120%); -webkit-backdrop-filter: blur(18px) saturate(120%);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  }
  .medichan :global(:is(input, select, textarea)) {
    background: rgba(10, 10, 26, 0.45); border-color: var(--border); border-radius: 14px;
    padding: 0.65rem 0.85rem; transition: border-color 0.4s;
  }
  .medichan :global(:is(input, select, textarea):focus) { outline: none; border-color: rgba(232, 207, 154, 0.55); }
  .medichan :global(textarea) { font-family: var(--sans); font-size: 1.05rem; line-height: 1.6; }
  .medichan :global(label) { color: var(--muted); font-size: 0.82rem; }
  .medichan :global(button) {
    border-radius: 999px; padding: 0.6rem 1.25rem; font-weight: 600;
    background: linear-gradient(135deg, #f0dcae, #d8b77a); border: 0; color: #2a2238;
    transition: transform 0.3s ease, box-shadow 0.4s ease, opacity 0.3s;
  }
  .medichan :global(button:not(:disabled):hover) { box-shadow: 0 0 24px rgba(232, 207, 154, 0.35); }
  .medichan :global(button.ghost) {
    background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border); color: var(--text); font-weight: 400;
  }
  .medichan :global(button.ghost:not(:disabled):hover) { border-color: rgba(232, 207, 154, 0.45); box-shadow: none; }
  .medichan :global(input[type='range']) { accent-color: var(--accent); background: none; border: 0; padding: 0; }
  .medichan :global(table th) { color: var(--muted); font-weight: 400; }
  .medichan :global(table :is(th, td)) { border-color: var(--border); }
  .medichan .tabs button { box-shadow: none; }

  /* ── lista "Minhas" ── */
  .list { display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fill, minmax(min(100%, 380px), 1fr)); }
  .item { display: flex; gap: 0.4rem; align-items: stretch; }
  .open {
    flex: 1; display: flex; gap: 0.9rem; align-items: center; text-align: left;
    background: var(--panel) !important; border: 1px solid var(--border) !important; color: var(--text) !important;
    border-radius: 18px !important; padding: 0.95rem 1.1rem !important; font-weight: 400 !important;
    backdrop-filter: blur(14px);
  }
  .open:hover { border-color: rgba(232, 207, 154, 0.45) !important; }
  .dot {
    flex: none; display: grid; place-items: center; width: 2.4rem; height: 2.4rem; border-radius: 50%;
    background: rgba(232, 207, 154, 0.14); color: var(--accent); font-size: 0.8rem;
  }
  .text { display: flex; flex-direction: column; gap: 0.2rem; min-width: 0; }
  .text strong { font-family: var(--serif); font-weight: 500; font-size: 1.25rem; }
  .feel { font-style: italic; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
  .actions { display: flex; flex-direction: column; gap: 0.4rem; }
  .icon-btn { width: 2.5rem; height: 100%; padding: 0 !important; color: var(--muted) !important; }
  .icon-btn.done { color: var(--sage) !important; }
  .small { font-size: 0.8rem; }
  .total { margin: 0 0 0.9rem; }
  .empty .link { background: none; padding: 0; color: var(--accent); text-decoration: underline; font-weight: 400; }
  .section-title { margin-top: 2rem !important; }
</style>
