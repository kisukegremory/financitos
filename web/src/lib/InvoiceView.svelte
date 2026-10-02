<script>
  import { api } from './api.js'
  import { dateBR, money, toTSV } from './format.js'
  import TransactionTable from './TransactionTable.svelte'

  let { categories, invoice = $bindable() } = $props()

  let source = $state('')
  let category = $state('')
  let items = $state([])
  let summary = $state(null)
  let payments = $state([])
  let balances = $state({}) // categoria -> saldo atual
  let paidAt = $state(new Date().toISOString().slice(0, 10))
  let message = $state('')

  async function load() {
    message = ''
    try {
      ;[items, summary, payments] = await Promise.all([
        api.list({ invoice, source, category }),
        api.summary(invoice, source),
        api.payments({ invoice, source }),
      ])
      balances = Object.fromEntries((await api.balances()).map((b) => [b.category, b]))
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

  async function payRemaining() {
    // sem filtro de fonte, paga cada cartão que tem lançamentos nessa fatura
    const sources = source
      ? [source]
      : [...new Set((await api.list({ invoice })).map((t) => t.source))]
    if (!confirm(`Registrar pagamento de ${money(summary.remaining)} (${sources.join(', ')})?`))
      return
    for (const s of sources) await api.pay(invoice, s, paidAt)
    load()
  }

  async function removePayment(p) {
    if (!confirm(`Desfazer pagamento de ${money(p.amount)} (${p.category})?`)) return
    await api.removePayment(p.id)
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
        {#if Number(c.paid)}
          <small class:done={Number(c.remaining) === 0}>
            {Number(c.remaining) === 0 ? '✓ pago' : `falta ${money(c.remaining)}`}
          </small>
        {/if}
        {#if balances[c.category]?.updated_at && Number(c.remaining) > 0}
          {@const after = Number(balances[c.category].amount) - Number(c.remaining)}
          <small class:negative-balance={after < 0} title="Saldo atual menos o que falta pagar">
            saldo após pagar {money(after)}
          </small>
        {/if}
      </button>
    {/each}
    <div class="card total">
      <span class="muted">Total</span>
      <strong>{money(summary.total)}</strong>
      <small>pago {money(summary.paid)}</small>
    </div>
  </section>

  <section class="row spread pay">
    {#if Number(summary.remaining) > 0}
      <strong>Falta pagar {money(summary.remaining)}</strong>
      <div class="row">
        <label>Data <input type="date" bind:value={paidAt} /></label>
        <button onclick={payRemaining}>Pagar o que falta</button>
      </div>
    {:else}
      <strong class="done">✓ Fatura quitada até agora</strong>
    {/if}
  </section>
{/if}

{#if payments.length}
  <details class="payments">
    <summary>Pagamentos ({payments.length}) · {money(summary?.paid ?? 0)}</summary>
    <table>
      <tbody>
        {#each payments as p (p.id)}
          <tr>
            <td>{dateBR(p.paid_at)}</td>
            <td>{p.category}</td>
            <td>{p.source}</td>
            <td class="num">{money(p.amount)}</td>
            <td><button class="ghost" title="Desfazer" onclick={() => removePayment(p)}>✕</button></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </details>
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
