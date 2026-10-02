<script>
  import { api } from './api.js'
  import { money, toTSV } from './format.js'
  import TransactionTable from './TransactionTable.svelte'

  let { categories, invoice = $bindable() } = $props()

  let source = $state('')
  let category = $state('')
  let items = $state([])
  let summary = $state(null)
  let message = $state('')

  async function load() {
    message = ''
    try {
      ;[items, summary] = await Promise.all([
        api.list({ invoice, source, category }),
        api.summary(invoice, source),
      ])
    } catch (e) {
      message = `Erro: ${e.message}`
    }
  }

  $effect(() => {
    invoice, source, category
    load()
  })

  async function changeCategory(item, c) {
    await api.update(item.id, { category: c })
    load()
  }

  async function changeNote(item, note) {
    await api.update(item.id, { note })
    item.note = note || null
  }

  async function remove(item) {
    if (!confirm(`Remover "${item.description}" (${money(item.amount)})?`)) return
    await api.remove(item.id)
    load()
  }

  async function copy() {
    await navigator.clipboard.writeText(toTSV(items))
    message = 'Copiado para a área de transferência'
  }
</script>

<section>
  <div class="row">
    <label>Fatura <input type="month" bind:value={invoice} /></label>
    <label>Fonte <input bind:value={source} placeholder="todas" /></label>
    <label>
      Caixinha
      <select bind:value={category}>
        <option value="">todas</option>
        {#each categories as c}<option>{c}</option>{/each}
      </select>
    </label>
  </div>
  {#if message}<p class="muted">{message}</p>{/if}
</section>

{#if summary?.categories.length}
  <section class="cards">
    {#each summary.categories as c}
      <button
        class="card"
        class:active={category === c.category}
        onclick={() => (category = category === c.category ? '' : c.category)}
      >
        <span class="muted">{c.category}</span>
        <strong>{money(c.total)}</strong>
      </button>
    {/each}
    <div class="card total">
      <span class="muted">Total</span>
      <strong>{money(summary.total)}</strong>
    </div>
  </section>
{/if}

<section>
  {#if items.length}
    <div class="row spread">
      <strong>{items.length} lançamentos</strong>
      <button class="ghost" onclick={copy}>Copiar TSV</button>
    </div>
    <TransactionTable
      {items}
      {categories}
      onchange={changeCategory}
      onnote={changeNote}
      onremove={remove}
    />
  {:else}
    <p class="muted">Nenhum lançamento nessa fatura.</p>
  {/if}
</section>
