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
      suggestions = await api.generate(hint, 3)
    } catch (e) {
      error = e.message
    } finally {
      generating = false
    }
  }

  async function keep(s) {
    if (await save({ text: s.text, author: s.author, origin: 'ai', prompt: hint || null }))
      suggestions = suggestions.filter((x) => x !== s)
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
    <textarea rows="3" placeholder="Tema ou dica (opcional): recomeço, coragem, saudade..." bind:value={hint}></textarea>
    <button disabled={generating} onclick={generate}>{generating ? 'Gerando…' : 'Gerar 3 sugestões'}</button>
    {#each suggestions as s (s.text)}
      <div class="suggestion">
        <blockquote>{s.text}</blockquote>
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
          {p.author ? `— ${p.author}` : ''}
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
</style>
