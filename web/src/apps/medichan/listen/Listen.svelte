<script>
  // Consumo: lista o que foi publicado e toca o arquivo final. Não importa nada do estúdio
  // além do catálogo, para poder virar o site/app externo sem arrasto.
  import { dateBR } from '../../../lib/format.js'
  import { duration, loadCatalog } from './catalog.js'
  import ListenPlayer from './ListenPlayer.svelte'

  let items = $state([])
  let error = $state('')
  let playing = $state(null)

  loadCatalog().then((c) => (items = c.items)).catch((e) => (error = e.message))
</script>

{#if playing}
  {#key playing}
    <ListenPlayer item={playing} onclose={() => (playing = null)} />
  {/key}
{:else}
  {#if error}<p class="error">{error}</p>{/if}
  {#if !items.length && !error}
    <p class="muted">Nada publicado ainda. Publique uma meditação em “Minhas”.</p>
  {/if}
  <div class="list">
    {#each items as item (item.slug)}
      <button class="ghost card" onclick={() => (playing = item)}>
        <strong>{item.access === 'private' ? '🔒 ' : ''}{item.title}</strong>
        {#if item.summary}<span class="muted">{item.summary}</span>{/if}
        <span class="muted small">
          {duration(item.duration_s)} · {dateBR(item.published_at.slice(0, 10))}
          {#each item.tags as t}<span class="tag">#{t}</span>{/each}
        </span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .list { display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); }
  .card {
    display: flex; flex-direction: column; align-items: flex-start; gap: 0.25rem;
    text-align: left; padding: 1.1rem 1.25rem !important; background: var(--panel) !important;
    border: 1px solid var(--border) !important; border-radius: 18px !important; color: var(--text) !important;
    backdrop-filter: blur(14px); font-weight: 400 !important;
  }
  .card strong { font-family: var(--serif); font-size: 1.35rem; font-weight: 500; }
  .card:hover { border-color: rgba(232, 207, 154, 0.45) !important; }
  .small { font-size: 0.8rem; }
  .tag { margin-left: 0.4rem; color: var(--sage); }
  .error { color: var(--danger); }
</style>
