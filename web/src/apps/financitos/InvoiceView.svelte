<script>
  import { api } from './api.js'
  import { dateBR, money, parseMoney, toTSV } from '../../lib/format.js'
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

  // soma só dos saldos já informados; null se nenhum foi informado ainda
  const totalBalance = $derived.by(() => {
    const informed = Object.values(balances).filter((b) => b.updated_at)
    return informed.length ? informed.reduce((s, b) => s + Number(b.amount), 0) : null
  })

  // % do saldo da caixinha que o valor em aberto da fatura consome
  function usageLevel(pct) {
    if (pct > 100) return 'over'
    if (pct >= 70) return 'high'
    return 'ok'
  }

  // --- simulador de compra (só no navegador, não grava nada) ---
  let simAmount = $state('')
  let simCategory = $state('')

  const simulation = $derived.by(() => {
    const amount = parseMoney(simAmount)
    const balance = balances[simCategory]
    if (!simCategory || amount === null || !balance?.updated_at) return null
    const open = Number(summary?.categories.find((c) => c.category === simCategory)?.remaining ?? 0)
    return { amount: Number(amount), open, balance: Number(balance.amount) }
  })

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

{#snippet usage(open, balance)}
  {@const pct = balance > 0 ? (open / balance) * 100 : Infinity}
  {@const level = usageLevel(pct)}
  <div class="usage {level}" title="Em aberto na fatura ÷ saldo atual da caixinha">
    <div class="bar"><span style:width="{Math.min(pct, 100)}%"></span></div>
    <small>
      {Number.isFinite(pct) ? `${pct.toFixed(0)}% do saldo` : 'sem saldo'} · sobra {money(balance - open)}
    </small>
  </div>
{/snippet}

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
          {@render usage(Number(c.remaining), Number(balances[c.category].amount))}
        {/if}
      </button>
    {/each}
    <div class="card total">
      <span class="muted">Total</span>
      <strong>{money(summary.total)}</strong>
      <small>pago {money(summary.paid)}</small>
      {#if Number(summary.remaining) > 0 && totalBalance !== null}
        {@render usage(Number(summary.remaining), totalBalance)}
      {/if}
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

<section class="simulator">
  <strong>Simular compra</strong>
  <div class="row">
    <label>Valor <input inputmode="decimal" placeholder="0,00" bind:value={simAmount} /></label>
    <label>
      Caixinha
      <select bind:value={simCategory}>
        <option value="" disabled>escolha</option>
        {#each categories as c}<option>{c}</option>{/each}
      </select>
    </label>
  </div>
  {#if simulation}
    {@const { amount, open, balance } = simulation}
    <div class="sim-result">
      <span class="muted">
        Saldo {money(balance)} − em aberto nesta fatura {money(open)} − compra {money(amount)}
      </span>
      {@render usage(open + amount, balance)}
    </div>
  {:else if simCategory && !balances[simCategory]?.updated_at}
    <p class="muted">Informe o saldo de {simCategory} na aba Caixinhas para simular.</p>
  {/if}
</section>

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
