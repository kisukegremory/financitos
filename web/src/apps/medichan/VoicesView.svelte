<script>
  import { usd } from '../../lib/format.js'
  import { preview, togglePreview } from './preview.svelte.js'

  let { voices, onpick } = $props()

  let sort = $state('provider')
  const sorters = {
    provider: (a, b) => a.provider.localeCompare(b.provider) || a.label.localeCompare(b.label),
    cost: (a, b) => a.estimate_usd - b.estimate_usd,
    pace: (a, b) => a.chars_per_sec - b.chars_per_sec,
  }
  // família = primeira palavra do provedor (Gemini, ElevenLabs, OpenAI, Microsoft...)
  const family = (v) => v.provider.split(' ')[0]
  let families = $derived([...new Set(voices.map(family))].sort())
  let only = $state('')
  let sorted = $derived(voices.filter((v) => !only || family(v) === only).sort(sorters[sort]))
</script>

<section>
  <div class="row spread">
    <div>
      <h2>Vozes</h2>
      <p class="muted small">
        Todas leem o mesmo trecho. O custo é estimado para uma meditação típica (~2.000 caracteres
        falados, uns 4 min); a geração real mostra o valor exato em “Minhas”.
      </p>
    </div>
    <div class="row">
    <label>
      modelo
      <select bind:value={only}>
        <option value="">todos ({voices.length})</option>
        {#each families as f (f)}<option value={f}>{f}</option>{/each}
      </select>
    </label>
    <label>
      ordenar por
      <select bind:value={sort}>
        <option value="provider">modelo</option>
        <option value="cost">custo</option>
        <option value="pace">ritmo (mais lento primeiro)</option>
      </select>
    </label>
    </div>
  </div>

  <table>
    <thead>
      <tr><th></th><th>Modelo</th><th>Voz</th><th>Ritmo</th><th class="num">Custo / meditação</th><th></th></tr>
    </thead>
    <tbody>
      {#each sorted as v (v.id)}
        <tr>
          <td>
            <button class="ghost play" title="ouvir amostra" onclick={() => togglePreview(v)}>
              {preview.id === v.id ? '■' : '▶'}
            </button>
          </td>
          <td>{v.provider}</td>
          <td>
            <strong>{v.label}</strong>
            <span class="muted small">{v.note}</span>
            {#if preview.error === v.id}<span class="error small">amostra não gerada</span>{/if}
          </td>
          <td>
            <span class="pace {v.pace}">{v.pace}</span>
            <span class="muted small">{v.chars_per_sec.toFixed(1)} car/s</span>
          </td>
          <td class="num">{usd(v.estimate_usd)}</td>
          <td><button class="ghost" onclick={() => onpick(v.id)}>usar</button></td>
        </tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  .small { font-size: 0.78rem; display: block; }
  .play { width: 2.2rem; padding: 0.3rem; }
  .pace { font-size: 0.8rem; padding: 0.1rem 0.5rem; border-radius: 999px; border: 1px solid var(--border); }
  .pace.lento { color: var(--accent); border-color: var(--accent); }
  .pace.rápido { color: #e8b04b; border-color: #e8b04b; }
  .error { color: var(--danger); }
  td { vertical-align: middle; }
  .play { height: 2.2rem; padding: 0 !important; }
  td strong { font-family: var(--serif); font-size: 1.15rem; font-weight: 500; }
  @media (max-width: 720px) {
    thead { display: none; }
    table, tbody { display: block; }
    tr {
      display: grid; grid-template-columns: auto 1fr auto; gap: 0.15rem 0.75rem; align-items: center;
      padding: 0.75rem 0; border-bottom: 1px solid var(--border);
    }
    td { border: 0; padding: 0; }
    td:nth-child(1) { grid-row: span 3; }
    td:nth-child(2) { grid-column: 2; color: var(--muted); font-size: 0.78rem; order: -1; }
    td:nth-child(3) { grid-column: 2; }
    td:nth-child(4) { grid-column: 2; }
    td:nth-child(5) { grid-column: 3; grid-row: 1; }
    td:nth-child(6) { grid-column: 3; grid-row: 2 / span 2; }
  }
</style>
