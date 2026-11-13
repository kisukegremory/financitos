<script>
  // Player de consumo: um <audio> nativo + Media Session (controles na tela de bloqueio).
  // Funciona em segundo plano no celular, ao contrário da mixagem ao vivo do estúdio.
  import { onDestroy } from 'svelte'
  import { sources } from './catalog.js'

  let { item, onclose } = $props()

  // svelte-ignore state_referenced_locally (valor inicial é o pretendido: o pai recria o componente)
  const POS_KEY = `medichan:pos:${item.slug}`
  let audio = $state()
  let srcs = $state([])
  let error = $state('')
  let paused = $state(true)
  let time = $state(0)
  // svelte-ignore state_referenced_locally (valor inicial é o pretendido: o pai recria o componente)
  let total = $state(item.duration_s)

  // svelte-ignore state_referenced_locally
  sources(item).then((s) => (srcs = s)).catch((e) => (error = e.message))

  function loaded() {
    const saved = Number(localStorage.getItem(POS_KEY))
    if (saved > 5 && saved < total - 15) audio.currentTime = saved // retoma de onde parou
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({ title: item.title, artist: 'medichan' })
      navigator.mediaSession.setActionHandler('play', () => audio.play())
      navigator.mediaSession.setActionHandler('pause', () => audio.pause())
      navigator.mediaSession.setActionHandler('seekbackward', () => seek(-15))
      navigator.mediaSession.setActionHandler('seekforward', () => seek(15))
    }
  }

  function seek(delta) {
    audio.currentTime = Math.min(Math.max(audio.currentTime + delta, 0), total)
  }

  function save() {
    localStorage.setItem(POS_KEY, String(Math.floor(time)))
  }

  function ended() {
    localStorage.removeItem(POS_KEY)
  }

  onDestroy(() => {
    if (audio && !audio.ended) save()
    for (const s of srcs) if (s.src.startsWith('blob:')) URL.revokeObjectURL(s.src)
  })

  const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
</script>

<section class="player">
  <div class="top"><button class="ghost" onclick={onclose}>← voltar</button></div>
  <h2>{item.title}</h2>
  {#if item.summary}<p class="muted summary">{item.summary}</p>{/if}

  <div class="stage"><div class="breath" class:running={!paused}></div></div>

  {#if error}<p class="error">{error}</p>{/if}
  {#if srcs.length}
    <audio
      bind:this={audio}
      bind:paused
      bind:currentTime={time}
      bind:duration={total}
      onloadedmetadata={loaded}
      onpause={save}
      onended={ended}
      preload="metadata"
    >
      {#each srcs as s}<source src={s.src} type={s.type} />{/each}
    </audio>
    <input
      class="seek"
      type="range"
      min="0"
      max={total || 0}
      step="1"
      bind:value={time}
      oninput={() => (audio.currentTime = time)}
    />
    <div class="row controls">
      <button class="ghost" onclick={() => seek(-15)}>⟲ 15</button>
      <button onclick={() => (paused ? audio.play() : audio.pause())}>
        {paused ? '▶ Ouvir' : '⏸ Pausar'}
      </button>
      <button class="ghost" onclick={() => seek(15)}>15 ⟳</button>
    </div>
    <p class="muted time">{clock(time)} / {clock(total || 0)}</p>
  {:else if !error}
    <p class="muted">carregando…</p>
  {/if}
</section>

<style>
  .player { display: flex; flex-direction: column; gap: 0.75rem; }
  .top { display: flex; }
  .player { background: transparent !important; border: 0 !important; box-shadow: none !important; backdrop-filter: none !important; }
  h2 { margin: 1rem 0 0 !important; text-align: center; font-size: clamp(1.8rem, 5vw, 2.6rem) !important; }
  .summary { text-align: center; margin: 0; }
  .stage { display: grid; place-items: center; min-height: 260px; }
  .breath {
    width: min(240px, 60vw); aspect-ratio: 1; border-radius: 50%;
    background: radial-gradient(circle, rgba(232, 207, 154, 0.32), rgba(169, 196, 176, 0.08) 55%, transparent 72%);
    border: 1px solid rgba(232, 207, 154, 0.28);
    box-shadow: 0 0 80px rgba(232, 207, 154, 0.18);
    transform: scale(0.7);
    animation: breathe 10s ease-in-out infinite;
    animation-play-state: paused;
  }
  .breath.running { animation-play-state: running; }
  @keyframes breathe {
    0% { transform: scale(0.7); opacity: 0.6; }
    40% { transform: scale(1.25); opacity: 1; }
    100% { transform: scale(0.7); opacity: 0.6; }
  }
  .seek { width: 100%; padding: 0; }
  .controls { justify-content: center; gap: 0.5rem; }
  .controls > button:not(.ghost) { padding: 0.8rem 2rem; font-size: 1.05rem; }
  .time { text-align: center; font-variant-numeric: tabular-nums; margin: 0; }
  .error { color: var(--danger); }
</style>
