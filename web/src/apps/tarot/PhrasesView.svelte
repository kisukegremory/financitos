<script>
  import { api } from './api.js'

  let phrases = $state([])
  let q = $state('')
  let onlyFavorites = $state(false)
  let error = $state('')

  let text = $state('')
  let author = $state('')

  let hint = $state('')
  let suggestions = $state([])
  let generating = $state(false)

  // modos: original (tom do prompt base), quote (citações reais), inspired (no estilo de alguém)
  let mode = $state('original')
  let thinker = $state('')
  let thinkers = $state([])
  let recommending = $state(false)
  const classics = ['Sun Tzu', 'Platão', 'Aristóteles', 'Sêneca', 'Marco Aurélio', 'Epicteto', 'Lao-Tsé', 'Confúcio', 'Buda', 'Rumi', 'Montaigne', 'Nietzsche', 'Schopenhauer', 'Kierkegaard', 'Camus', 'Miyamoto Musashi']

  async function load() {
    phrases = await api.phrases({ q, favorite: onlyFavorites ? true : undefined })
  }

  $effect(() => {
    q, onlyFavorites
    load().catch((e) => (error = e.message))
  })

  async function save(phrase) {
    error = ''
    try {
      await api.createPhrase(phrase)
      await load()
      return true
    } catch (e) {
      error = e.message
    }
  }

  async function addManual() {
    if (await save({ text, author: author || null })) text = author = ''
  }

  async function generate() {
    error = ''
    generating = true
    try {
      suggestions = await api.generate({ hint: hint || null, count: 3, mode, thinker: thinker || null })
    } catch (e) {
      error = e.message
    } finally {
      generating = false
    }
  }

  async function keep(s) {
    const prompt = [thinker, hint].filter(Boolean).join(' · ') || null
    if (await save({ text: s.text, author: s.author, source: s.source, origin: 'ai', prompt }))
      suggestions = suggestions.filter((x) => x !== s)
  }

  async function recommend() {
    error = ''
    recommending = true
    try {
      thinkers = await api.recommendThinkers(hint)
    } catch (e) {
      error = e.message
    } finally {
      recommending = false
    }
  }

  function pick(t) {
    thinker = t.name
    if (mode === 'original') mode = 'quote'
  }

  async function toggleFavorite(p) {
    await api.updatePhrase(p.id, { favorite: !p.favorite })
    await load()
  }

  async function remove(p) {
    if (!confirm(`Apagar "${p.text}"?`)) return
    await api.removePhrase(p.id)
    await load()
  }
</script>

{#if error}<p class="error">{error}</p>{/if}

<div class="two">
  <section>
    <h2>Guardar uma frase</h2>
    <textarea rows="3" placeholder="A frase que te marcou..." bind:value={text}></textarea>
    <div class="row">
      <input placeholder="Autor (opcional)" bind:value={author} />
      <button disabled={!text.trim()} onclick={addManual}>Guardar</button>
    </div>
  </section>

  <section>
    <h2>Gerar com IA</h2>
    <div class="modes">
      <label class="inline"><input type="radio" bind:group={mode} value="original" /> Original</label>
      <label class="inline"><input type="radio" bind:group={mode} value="quote" /> Citação real</label>
      <label class="inline"><input type="radio" bind:group={mode} value="inspired" /> Inspirada em</label>
    </div>
    {#if mode !== 'original'}
      <input
        class="thinker"
        list="classics"
        placeholder={mode === 'quote' ? 'Pensador (vazio = a IA escolhe)' : 'Pensador: Sun Tzu, Sêneca...'}
        bind:value={thinker}
      />
      <datalist id="classics">
        {#each classics as c (c)}<option value={c}></option>{/each}
      </datalist>
    {/if}
    <textarea rows="3" placeholder="Tema ou dica (opcional): recomeço, coragem, saudade..." bind:value={hint}></textarea>
    <div class="row">
      <button disabled={generating || (mode === 'inspired' && !thinker.trim())} onclick={generate}>
        {generating ? 'Gerando…' : 'Gerar 3 sugestões'}
      </button>
      <button class="ghost" disabled={recommending} onclick={recommend}>
        {recommending ? 'Pensando…' : '🏛 Sugerir pensadores'}
      </button>
    </div>
    {#if mode === 'quote'}
      <p class="muted small">A IA pode errar atribuições: confira a fonte antes de guardar.</p>
    {/if}
    {#if thinkers.length}
      <div class="thinkers">
        {#each thinkers as t (t.name)}
          <button class="ghost thinker-card" class:active={thinker === t.name} onclick={() => pick(t)}>
            <strong>{t.name}</strong> <span class="muted">{t.era}</span>
            <span>{t.why}</span>
            <span class="muted small">📚 {t.works.join(' · ')}</span>
          </button>
        {/each}
      </div>
    {/if}
    {#each suggestions as s (s.text)}
      <div class="suggestion">
        <blockquote>{s.text}</blockquote>
        {#if s.author || s.source}
          <p class="muted small">— {s.author ?? ""}{s.author && s.source ? ", " : ""}{#if s.source}<i>{s.source}</i>{/if}</p>
        {/if}
        <div class="row">
          <button onclick={() => keep(s)}>Guardar</button>
          <button class="ghost" onclick={() => (suggestions = suggestions.filter((x) => x !== s))}>Descartar</button>
        </div>
      </div>
    {/each}
  </section>
</div>

<section>
  <div class="row spread">
    <h2>Minhas frases <span class="muted">({phrases.length})</span></h2>
    <div class="row">
      <input type="search" placeholder="Buscar" bind:value={q} />
      <label class="inline"><input type="checkbox" bind:checked={onlyFavorites} /> só favoritas</label>
    </div>
  </div>
  {#each phrases as p (p.id)}
    <article class="phrase">
      <blockquote>{p.text}</blockquote>
      <div class="row spread meta">
        <span class="muted">
          {p.author ? `— ${p.author}` : ''}{p.source ? `, ${p.source}` : ''}
          {#if p.origin === 'ai'}<span class="tag">✨ IA{p.prompt ? `: ${p.prompt}` : ''}</span>{/if}
        </span>
        <span class="row">
          <button class="ghost icon" title="Favoritar" onclick={() => toggleFavorite(p)}>{p.favorite ? '★' : '☆'}</button>
          <button class="ghost icon" title="Apagar" onclick={() => remove(p)}>🗑</button>
        </span>
      </div>
    </article>
  {:else}
    <p class="muted">Nenhuma frase ainda.</p>
  {/each}
</section>

<style>
  .two { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
  .two section { margin-bottom: 0; }
  .two + section { margin-top: 1rem; }
  h2 { font-size: 1rem; margin: 0 0 0.25rem; }
  textarea { font-family: inherit; font-size: 0.95rem; }
  blockquote { margin: 0; font-size: 1.05rem; font-style: italic; line-height: 1.5; }
  .suggestion { border-top: 1px solid var(--border); padding-top: 0.75rem; margin-top: 0.75rem; }
  .suggestion .row { margin-top: 0.5rem; }
  .phrase { border-top: 1px solid var(--border); padding: 0.75rem 0; }
  .meta { margin: 0.25rem 0 0; font-size: 0.85rem; }
  .tag { margin-left: 0.5rem; color: var(--accent); }
  .icon { padding: 0.2rem 0.45rem; }
  label.inline { flex-direction: row; align-items: center; }
  .error { color: var(--danger); }
  .modes { display: flex; gap: 1rem; margin: 0.5rem 0; }
  .thinker { width: 100%; box-sizing: border-box; }
  .small { font-size: 0.8rem; margin: 0.4rem 0 0; }
  .thinkers { display: grid; gap: 0.5rem; margin-top: 0.75rem; }
  .thinker-card {
    display: flex; flex-direction: column; align-items: flex-start; gap: 0.2rem;
    text-align: left; padding: 0.6rem 0.75rem;
  }
  .thinker-card.active { border-color: var(--accent); }
</style>
