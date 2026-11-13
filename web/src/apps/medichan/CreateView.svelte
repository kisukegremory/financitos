<script>
  import { usd } from '../../lib/format.js'
  import { api } from './api.js'
  import { preview, togglePreview } from './preview.svelte.js'

  let { voices, voice = $bindable(), onready } = $props()

  const SUGGESTIONS = [
    'ansiedade', 'cansaço', 'gratidão', 'uma decisão difícil',
    'saudade', 'raiva que não passa', 'falta de foco', 'recomeço',
  ]

  let feeling = $state('')
  let loading = $state(false)
  let error = $state('')

  // vozes agrupadas por modelo no seletor
  let groups = $derived(
    Object.entries(Object.groupBy(voices, (v) => v.provider)).sort(([a], [b]) => a.localeCompare(b)),
  )
  let selected = $derived(voices.find((v) => v.id === voice))

  function suggest(word) {
    feeling = feeling.trim() ? `${feeling.trim()}, ${word}` : word
  }

  async function create() {
    error = ''
    loading = true
    try {
      onready(await api.create(feeling.trim(), voice))
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }
</script>

<section>
  <h2>Como você está se sentindo agora?</h2>
  <p class="muted lead">Sem pressa. Escreva como vier, mesmo que sejam só algumas palavras.</p>
  <textarea
    rows="4"
    placeholder="Escreva com suas palavras o que está sentindo ou pensando..."
    bind:value={feeling}
    disabled={loading}
    onkeydown={(e) => e.key === 'Enter' && (e.ctrlKey || e.metaKey) && feeling.trim() && create()}
  ></textarea>
  <div class="chips">
    {#each SUGGESTIONS as s (s)}
      <button class="ghost chip" disabled={loading} onclick={() => suggest(s)}>{s}</button>
    {/each}
  </div>

  <div class="row">
    <label class="voice">
      voz
      <select bind:value={voice} disabled={loading}>
        {#each groups as [provider, list] (provider)}
          <optgroup label={provider}>
            {#each list as v (v.id)}
              <option value={v.id}>{v.label} — {v.note} · {usd(v.estimate_usd)}</option>
            {/each}
          </optgroup>
        {/each}
      </select>
    </label>
    {#if selected}
      <button class="ghost" title="ouvir amostra" onclick={() => togglePreview(selected)}>
        {preview.id === selected.id ? '■ parar' : '▶ amostra'}
      </button>
    {/if}
  </div>

  {#if selected}
    <p class="muted info">
      {selected.provider} · ritmo <strong>{selected.pace}</strong> ({selected.chars_per_sec.toFixed(1)} car/s) ·
      custo estimado <strong>{usd(selected.estimate_usd)}</strong> por meditação
      {#if preview.error === selected.id}<span class="error"> · amostra não gerada</span>{/if}
    </p>
  {/if}

  <button class="go" class:loading disabled={!feeling.trim() || loading || !voice} onclick={create}>
    {loading ? 'escrevendo e dando voz… (~30 s)' : '✿ criar minha meditação'}
  </button>
  {#if error}<p class="error">{error}</p>{/if}
</section>

<style>
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1rem; }
  .chip { font-size: 0.85rem; padding: 0.35rem 0.9rem !important; border-radius: 999px; }
  .chip:hover { color: var(--accent) !important; }
  .row { align-items: flex-end; }
  .voice { flex: 1; min-width: 0; }
  .voice select { width: 100%; max-width: 100%; text-overflow: ellipsis; }
  .info { font-size: 0.82rem; margin: 0.5rem 0 1rem; }
  .info strong { color: var(--text); font-weight: 500; }
  .go { width: 100%; padding: 0.9rem !important; font-size: 1.05rem; }
  .lead { margin: 0 0 0.25rem; }
  .loading { animation: pulse 2.4s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: 0.55; } }
  .error { color: var(--danger); }
</style>
