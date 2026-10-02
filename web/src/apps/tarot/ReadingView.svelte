<script>
  import { dateBR } from '../../lib/format.js'
  import { api } from './api.js'
  import TarotCard from './TarotCard.svelte'

  let feeling = $state('')
  let reading = $state(null)
  let history = $state([])
  let loading = $state(false)
  let error = $state('')
  let kept = $state(false)

  api.readings().then((r) => (history = r))

  async function read() {
    error = ''
    loading = true
    kept = false
    try {
      reading = await api.read(feeling)
      history = [reading, ...history]
      feeling = ''
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  async function keepPhrase() {
    await api.createPhrase({ text: reading.generated_text, origin: 'ai', prompt: reading.feeling })
    kept = true
  }

  async function remove(r) {
    if (!confirm('Apagar esta leitura?')) return
    await api.removeReading(r.id)
    history = history.filter((x) => x.id !== r.id)
    if (reading?.id === r.id) reading = null
  }

  const phraseText = (r) => r.phrase?.text ?? r.generated_text ?? '(frase apagada)'
</script>

<section>
  <h2>Como você está hoje?</h2>
  <textarea
    rows="4"
    placeholder="Escreva o que está sentindo ou passando..."
    bind:value={feeling}
    onkeydown={(e) => e.key === 'Enter' && (e.ctrlKey || e.metaKey) && feeling.trim() && read()}
  ></textarea>
  <div class="row">
    <button disabled={!feeling.trim() || loading} onclick={read}>
      {loading ? 'Lendo o momento…' : 'Buscar minha frase e carta'}
    </button>
    <span class="muted">Ctrl+Enter</span>
  </div>
  {#if error}<p class="error">{error}</p>{/if}
</section>

{#if reading}
  {#key reading.id}
    <div class="reading">
      <section class="phrase-side">
        <p class="muted feeling">“{reading.feeling}”</p>
        <blockquote>{phraseText(reading)}</blockquote>
        {#if reading.phrase?.author}<p class="muted">— {reading.phrase.author}</p>{/if}
        {#if reading.generated_text}
          <p class="row">
            <span class="tag">✨ frase nova, nenhuma da coleção encaixou</span>
            <button class="ghost" disabled={kept} onclick={keepPhrase}>{kept ? 'Guardada' : 'Guardar na coleção'}</button>
          </p>
        {/if}
        <h3>Como se relaciona</h3>
        <p>{reading.why}</p>
        <h3>A carta no seu momento</h3>
        <p>{reading.card_reading}</p>
      </section>
      <section class="card-side">
        <TarotCard draw={reading.draw} />
      </section>
    </div>
  {/key}
{/if}

{#if history.length}
  <section>
    <h2>Leituras anteriores</h2>
    {#each history as r (r.id)}
      <details class="past">
        <summary>
          <span class="muted">{dateBR(r.created_at.slice(0, 10))}</span>
          <span class="summary-text">{r.feeling}</span>
          <span class="muted">{r.draw.card.name}{r.draw.reversed ? ' (inv.)' : ''}</span>
        </summary>
        <blockquote>{phraseText(r)}</blockquote>
        <p>{r.why}</p>
        <p><strong>{r.draw.card.name}:</strong> {r.card_reading}</p>
        <button class="ghost" onclick={() => remove(r)}>Apagar</button>
      </details>
    {/each}
  </section>
{/if}

<style>
  h2 { font-size: 1rem; margin: 0 0 0.25rem; }
  h3 { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent); margin: 1.25rem 0 0.25rem; }
  textarea { font-family: inherit; font-size: 0.95rem; }
  .reading {
    display: grid; grid-template-columns: minmax(0, 3fr) minmax(260px, 2fr); gap: 1rem;
    animation: appear 0.5s ease-out;
  }
  @media (max-width: 760px) { .reading { grid-template-columns: 1fr; } }
  @keyframes appear { from { opacity: 0; transform: translateY(12px); } }
  .feeling { font-style: italic; margin-top: 0; }
  blockquote { margin: 0.5rem 0; font-size: 1.4rem; line-height: 1.45; font-style: italic; }
  p { line-height: 1.6; }
  .tag { color: var(--accent); font-size: 0.85rem; }
  .past { border-top: 1px solid var(--border); padding: 0.6rem 0; }
  .past summary { cursor: pointer; display: flex; gap: 0.75rem; align-items: baseline; }
  .summary-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .past blockquote { font-size: 1.05rem; }
  .error { color: var(--danger); }
</style>
