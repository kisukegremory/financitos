<script>
  import { dateBR } from '../../lib/format.js'
  import { api } from './api.js'
  import TarotCard from './TarotCard.svelte'

  let feeling = $state('')
  let reading = $state(null)
  let history = $state([])
  let loading = $state(false)
  let error = $state('')
  // textos já na coleção, para marcar o que foi guardado
  let saved = $state(new Set())

  api.readings().then((r) => (history = r))
  api.phrases().then((p) => (saved = new Set(p.map((x) => x.text))))

  async function read() {
    error = ''
    loading = true
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

  async function keep(phrase) {
    if (saved.has(phrase.text)) return
    await api.createPhrase({ ...phrase, origin: 'ai', prompt: reading.feeling })
    saved = new Set([...saved, phrase.text])
  }

  async function keepAll() {
    for (const q of reading.quotes) await keep(q)
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
      {loading ? 'Consultando pensadores e cartas…' : 'Fazer minha leitura'}
    </button>
    <span class="muted">Ctrl+Enter</span>
  </div>
  {#if error}<p class="error">{error}</p>{/if}
</section>

{#if reading}
  {#key reading.id}
    <p class="feeling">“{reading.feeling}”</p>

    <div class="reading">
      <div class="left">
        {#if reading.thinker}
          <section class="thinker">
            <span class="kicker">🏛 Um pensador para hoje</span>
            <h3>{reading.thinker.name} <span class="muted era">{reading.thinker.era}</span></h3>
            <p>{reading.thinker.why}</p>
            <p class="muted small">📚 {reading.thinker.works.join(' · ')}</p>

            {#each reading.quotes as q (q.text)}
              <div class="quote">
                <blockquote>{q.text}</blockquote>
                <div class="row spread">
                  <span class="muted small">{#if q.source}<i>{q.source}</i>{/if}</span>
                  <button class="ghost small-btn" disabled={saved.has(q.text)} onclick={() => keep(q)}>
                    {saved.has(q.text) ? '✓ Guardada' : 'Guardar'}
                  </button>
                </div>
              </div>
            {/each}
            {#if reading.quotes.some((q) => !saved.has(q.text))}
              <button class="ghost" onclick={keepAll}>Guardar todas</button>
            {/if}
            <p class="muted small">Citações trazidas pela IA podem ter atribuição errada: confira a fonte.</p>
          </section>
        {/if}

        <section>
          <span class="kicker">📖 Do seu livro de frases</span>
          {#if reading.generated_text}
            <blockquote class="big">{reading.generated_text}</blockquote>
            <div class="row">
              <span class="muted small">✨ nenhuma da coleção encaixou: frase nova</span>
              <button
                class="ghost small-btn"
                disabled={saved.has(reading.generated_text)}
                onclick={() => keep({ text: reading.generated_text })}
              >
                {saved.has(reading.generated_text) ? '✓ Guardada' : 'Guardar'}
              </button>
            </div>
          {:else}
            <blockquote class="big">{phraseText(reading)}</blockquote>
            {#if reading.phrase?.author}
              <p class="muted small">— {reading.phrase.author}{reading.phrase.source ? `, ${reading.phrase.source}` : ''}</p>
            {/if}
          {/if}
          <h4>Como se relaciona</h4>
          <p>{reading.why}</p>
        </section>
      </div>

      <section class="card-side">
        <span class="kicker">🔮 Sua carta</span>
        <TarotCard draw={reading.draw} reveal />
        <h4>A carta no seu momento</h4>
        <p>{reading.card_reading}</p>
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
        <div class="past-body">
          <TarotCard draw={r.draw} compact />
          <div>
            <blockquote>{phraseText(r)}</blockquote>
            <p>{r.why}</p>
            {#if r.thinker}
              <p><strong>🏛 {r.thinker.name}:</strong> {r.thinker.why}</p>
              {#each r.quotes as q (q.text)}<blockquote class="small-quote">{q.text}</blockquote>{/each}
            {/if}
            <p><strong>{r.draw.card.name}:</strong> {r.card_reading}</p>
            <button class="ghost" onclick={() => remove(r)}>Apagar</button>
          </div>
        </div>
      </details>
    {/each}
  </section>
{/if}

<style>
  h2 { font-size: 1rem; margin: 0 0 0.25rem; }
  h3 { font-family: Georgia, 'Times New Roman', serif; font-weight: 400; font-size: 1.5rem; margin: 0.3rem 0; }
  h4 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); margin: 1.25rem 0 0.25rem; }
  textarea { font-family: inherit; font-size: 0.95rem; }
  p { line-height: 1.6; }
  .kicker { font-size: 0.75rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
  .feeling { text-align: center; font-style: italic; color: var(--muted); margin: 0 0 1rem; }
  .era { font-family: system-ui, sans-serif; font-size: 0.85rem; }
  .small { font-size: 0.8rem; }
  .small-btn { padding: 0.2rem 0.6rem; font-size: 0.85rem; }

  .reading {
    display: grid; grid-template-columns: minmax(0, 3fr) minmax(280px, 2fr); gap: 1rem; align-items: start;
    animation: appear 0.5s ease-out;
  }
  @media (max-width: 800px) { .reading { grid-template-columns: 1fr; } }
  @keyframes appear { from { opacity: 0; transform: translateY(12px); } }
  .card-side {
    position: sticky; top: 1rem; text-align: center;
    background: radial-gradient(ellipse at top, rgba(180, 140, 255, 0.14), transparent 65%), var(--panel);
  }
  .card-side p { text-align: left; }
  .card-side .kicker { display: block; margin-bottom: 1rem; }

  .thinker { border-color: rgba(180, 140, 255, 0.45); }
  blockquote { margin: 0.5rem 0; font-style: italic; line-height: 1.5; font-family: Georgia, 'Times New Roman', serif; }
  blockquote.big { font-size: 1.4rem; }
  .quote { border-left: 2px solid var(--accent); padding: 0.2rem 0 0.2rem 0.9rem; margin: 0.9rem 0; }
  .quote blockquote { font-size: 1.1rem; margin: 0 0 0.3rem; }

  .past { border-top: 1px solid var(--border); padding: 0.6rem 0; }
  .past summary { cursor: pointer; display: flex; gap: 0.75rem; align-items: baseline; }
  .summary-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .past-body { display: grid; grid-template-columns: 160px 1fr; gap: 1.25rem; margin-top: 0.75rem; }
  @media (max-width: 600px) { .past-body { grid-template-columns: 1fr; } }
  .past blockquote { font-size: 1.05rem; }
  .small-quote { font-size: 0.95rem !important; color: var(--muted); }
  .error { color: var(--danger); }
</style>
