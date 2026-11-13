<script>
  import { onDestroy } from 'svelte'
  import { usd } from '../../lib/format.js'
  import { createAmbient, createTrackBed, seedFrom } from './ambient.js'
  import { loadAudio } from './api.js'
  import { createMediaSession } from './media-session.js'

  let { meditation, voiceName, tracks = [], onclose } = $props()

  // trilha de fundo: 'ambient' (gerada no navegador) ou o id de uma música do Lyria
  const BED_KEY = 'medichan:bed'
  // última escolha salva, se a música ainda existir
  function savedBed() {
    const saved = localStorage.getItem(BED_KEY)
    return saved && tracks.some((t) => String(t.id) === saved) ? saved : 'ambient'
  }
  let bed = $state(savedBed())
  let bedBuffer = null
  let bedLoading = $state(false)

  const LEAD = 6 // s só de trilha antes da primeira fala
  const GAP = 1.2 // s entre falas seguidas
  const TAIL = 10 // s de trilha no fim, com fade
  const DUCK = 0.35 // volume da trilha enquanto a voz fala

  let status = $state('loading') // loading | ready | playing | paused | ended
  let error = $state('')
  let loaded = $state(0)
  let elapsed = $state(0)
  let musicVolume = $state(0.7)
  let showScript = $state(false)
  let showFeeling = $state(false)

  let buffers = [] // AudioBuffer por trecho (null nas pausas); vale para qualquer AudioContext
  let timeline = $state([]) // [{index, kind, text, start, end}]
  let total = $state(0)
  let ctx = null
  let musicGain = null
  let t0 = 0
  let raf = 0
  let media = null // botões do fone

  let speechCount = $derived(meditation.segments.filter((s) => s.audio).length)

  async function prepare() {
    const decoder = new AudioContext()
    try {
      buffers = await Promise.all(
        meditation.segments.map(async (s) => {
          if (!s.audio) return null
          const buf = await decoder.decodeAudioData(await loadAudio(s.audio))
          loaded++
          return buf
        }),
      )
      buildTimeline()
      status = 'ready'
    } catch (e) {
      error = e.message
    } finally {
      decoder.close()
    }
  }

  function buildTimeline() {
    let t = LEAD
    let prev = null
    timeline = meditation.segments.map((s, index) => {
      if (s.kind === 'speech' && prev === 'speech') t += GAP
      const length = s.kind === 'speech' ? buffers[index].duration : s.seconds
      const item = { index, kind: s.kind, text: s.text, start: t, end: t + length }
      t += length
      prev = s.kind
      return item
    })
    total = t + TAIL
  }

  // baixa e decodifica a música escolhida antes de começar
  $effect(() => {
    localStorage.setItem(BED_KEY, bed)
    bedBuffer = null
    if (bed === 'ambient') return
    const track = tracks.find((t) => String(t.id) === bed)
    if (!track) return
    bedLoading = true
    const decoder = new AudioContext()
    loadAudio(track.audio)
      .then((data) => decoder.decodeAudioData(data))
      .then((buf) => (bedBuffer = buf))
      .catch((e) => (error = e.message))
      .finally(() => {
        bedLoading = false
        decoder.close()
      })
  })

  function start() {
    ctx = new AudioContext()
    t0 = ctx.currentTime + 0.15

    // trilha -> ducking (automático) -> volume (usuário) -> saída
    const ambient = bedBuffer
      ? createTrackBed(ctx, bedBuffer)
      : createAmbient(ctx, seedFrom(meditation.title))
    const duck = ctx.createGain()
    musicGain = ctx.createGain()
    musicGain.gain.value = musicVolume
    ambient.output.connect(duck).connect(musicGain).connect(ctx.destination)
    ambient.start(t0)
    ambient.fadeOut(t0 + total - TAIL + 2, TAIL - 2)

    const voice = ctx.createGain()
    voice.gain.value = 1
    voice.connect(ctx.destination)
    for (const item of timeline) {
      if (item.kind !== 'speech') continue
      const src = ctx.createBufferSource()
      src.buffer = buffers[item.index]
      src.connect(voice)
      src.start(t0 + item.start)
      // trilha abaixa um pouco antes da fala e volta devagar no silêncio
      duck.gain.setTargetAtTime(DUCK, t0 + item.start - 0.8, 0.3)
      duck.gain.setTargetAtTime(1, t0 + item.end + 0.4, 1.5)
    }
    status = 'playing'
    mediaControls().playing()
    tick()
  }

  function mediaControls() {
    media ??= createMediaSession({
      title: meditation.title,
      artwork: '/medichan/art/player.webp',
      onplay: () => status === 'paused' ? toggle() : (status === 'ready' || status === 'ended') && start(),
      onpause: () => status === 'playing' && toggle(),
    })
    return media
  }

  function tick() {
    elapsed = Math.min(ctx.currentTime - t0, total)
    if (elapsed >= total) return finish()
    raf = requestAnimationFrame(tick)
  }

  function finish() {
    cancelAnimationFrame(raf)
    ctx?.close()
    ctx = null
    status = 'ended'
    media?.paused()
  }

  async function toggle() {
    if (status === 'ready' || status === 'ended') return start()
    if (status === 'playing') {
      await ctx.suspend() // congela voz, trilha e relógio juntos
      status = 'paused'
      media?.paused()
    } else if (status === 'paused') {
      await ctx.resume()
      status = 'playing'
      media?.playing()
    }
  }

  $effect(() => {
    musicGain?.gain.setTargetAtTime(musicVolume, musicGain.context.currentTime, 0.1)
  })

  onDestroy(() => {
    media?.destroy()
    cancelAnimationFrame(raf)
    ctx?.close()
  })

  prepare()

  // trecho atual: o que está tocando ou, entre trechos, o último que começou
  let current = $derived(timeline.findLast((i) => i.start <= elapsed) ?? null)
  let lastSpoken = $derived(
    current ? timeline.slice(0, current.index + 1).findLast((i) => i.kind === 'speech') : null,
  )
  let silenceLeft = $derived(current?.kind === 'pause' ? Math.ceil(current.end - elapsed) : 0)

  const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
</script>

<section class="player">
  <div class="top">
    <button class="ghost" onclick={onclose}>← voltar</button>
    <span class="muted small">
      🎙 {voiceName}{#if meditation.cost_usd != null} · {usd(meditation.cost_usd)}{/if}
    </span>
  </div>

  <h2>{meditation.title}</h2>
  <button class="feeling" class:open={showFeeling} onclick={() => (showFeeling = !showFeeling)}
    title={showFeeling ? 'recolher' : 'ver tudo'}>“{meditation.feeling}”</button>

  <div class="stage">
    <div class="breath" class:running={status === 'playing'}></div>
    <div class="caption">
      {#if error}
        <p class="error">{error}</p>
      {:else if status === 'loading'}
        <p class="muted">carregando a voz… {loaded}/{speechCount}</p>
      {:else if status === 'ready'}
        <p class="muted">Encontre um lugar confortável. Quando quiser, comece.</p>
      {:else if status === 'ended'}
        <p class="muted">Fim. Leve com você o que ficou.</p>
      {:else if !current}
        <p class="muted">acomode-se…</p>
      {:else if current.kind === 'speech'}
        {#key current.index}<p class="spoken">{current.text}</p>{/key}
      {:else}
        {#if lastSpoken}<p class="spoken faded">{lastSpoken.text}</p>{/if}
        <p class="muted small">silêncio · {silenceLeft}s</p>
      {/if}
    </div>
  </div>

  <div class="progress"><div style:width="{total ? (elapsed / total) * 100 : 0}%"></div></div>

  <div class="row controls">
    <button disabled={status === 'loading' || bedLoading || !!error} onclick={toggle}>
      {status === 'playing' ? '❚❚ pausar' : status === 'paused' ? '▶ continuar' : status === 'ended' ? '↻ de novo' : '▶ começar'}
    </button>
    <span class="muted time">{clock(elapsed)} / {clock(total)}</span>
    {#if status === 'ready' || status === 'ended'}
      <label class="volume">
        fundo
        <select bind:value={bed} disabled={bedLoading}>
          <option value="ambient">gerada no navegador</option>
          {#each tracks as t (t.id)}<option value={String(t.id)}>🎶 {t.title}</option>{/each}
        </select>
      </label>
    {/if}
    <label class="volume">
      trilha
      <input type="range" min="0" max="1" step="0.05" bind:value={musicVolume} />
    </label>
  </div>

  <button class="ghost small" onclick={() => (showScript = !showScript)}>
    {showScript ? 'esconder roteiro' : 'ver roteiro'}
  </button>
  {#if showScript}
    <ol class="script">
      {#each meditation.segments as s, i (i)}
        <li class:now={current?.index === i && status !== 'ended'} class:pause={s.kind === 'pause'}>
          {s.kind === 'speech' ? s.text : `… ${s.seconds}s de silêncio`}
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .player { display: flex; flex-direction: column; gap: 0.75rem; }
  .top { display: flex; justify-content: space-between; align-items: center; }
  h2 { margin: 1rem 0 0 !important; text-align: center; font-size: clamp(1.8rem, 5vw, 2.6rem) !important; }
  .feeling {
    all: unset; cursor: pointer; display: -webkit-box; -webkit-box-orient: vertical;
    -webkit-line-clamp: 3; line-clamp: 3; overflow: hidden;
    max-width: 640px; margin: 0 auto; text-align: center; font-style: italic; color: var(--muted);
  }
  .feeling.open { display: block; }
  .small { font-size: 0.8rem; }

  .stage {
    position: relative; display: grid; place-items: center;
    min-height: min(52vh, 440px); overflow: hidden;
  }
  .breath {
    position: absolute; width: min(260px, 62vw); aspect-ratio: 1; border-radius: 50%;
    background: radial-gradient(circle, rgba(232, 207, 154, 0.32), rgba(169, 196, 176, 0.08) 55%, transparent 72%);
    border: 1px solid rgba(232, 207, 154, 0.28);
    box-shadow: 0 0 80px rgba(232, 207, 154, 0.18), inset 0 0 40px rgba(232, 207, 154, 0.12);
    transform: scale(0.7);
    animation: breathe 10s ease-in-out infinite; /* inspira 4s, solta 6s */
    animation-play-state: paused;
  }
  .breath.running { animation-play-state: running; }
  @keyframes breathe {
    0% { transform: scale(0.7); opacity: 0.6; }
    40% { transform: scale(1.25); opacity: 1; }
    100% { transform: scale(0.7); opacity: 0.6; }
  }
  .caption { position: relative; max-width: 560px; text-align: center; padding: 0 1rem; }
  .spoken {
    font-family: var(--serif); font-size: clamp(1.35rem, 3.6vw, 1.75rem); line-height: 1.5; margin: 0;
    animation: fade 1.8s ease; text-shadow: 0 2px 20px rgba(0, 0, 0, 0.6);
  }
  .spoken.faded { opacity: 0.35; }
  @keyframes fade { from { opacity: 0; } }

  .player { background: transparent !important; border: 0 !important; box-shadow: none !important; backdrop-filter: none !important; padding: 1rem 0 !important; }
  .controls > button:not(.ghost) { padding: 0.8rem 2rem; font-size: 1.05rem; }
  .progress { height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
  .progress div { height: 100%; background: var(--accent); transition: width 0.25s linear; }
  .controls { justify-content: center; }
  .time { font-variant-numeric: tabular-nums; }
  .volume { flex-direction: row; align-items: center; gap: 0.5rem; }
  .volume input { padding: 0; }
  button.small { align-self: center; font-size: 0.8rem; }

  .script { background: var(--panel); border-radius: 18px; padding: 1rem 1rem 1rem 2.2rem; backdrop-filter: blur(14px); color: var(--muted); line-height: 1.6; font-size: 0.9rem; }
  .script li.pause { font-style: italic; opacity: 0.6; list-style: none; }
  .script li.now { color: var(--accent); }
  .error { color: var(--danger); }
</style>
