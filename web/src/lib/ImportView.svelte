<script>
  import { api } from './api.js'
  import { currentMonth, money, toTSV } from './format.js'
  import { bankPrompt } from './prompts.js'
  import TransactionTable from './TransactionTable.svelte'

  let { categories, onsaved } = $props()

  let text = $state('')
  let source = $state('PicPay')
  let invoice = $state(currentMonth())
  let items = $state([])
  let loading = $state(false)
  let message = $state('')

  const total = $derived(items.reduce((s, t) => s + Number(t.amount), 0))

  async function categorize() {
    loading = true
    message = ''
    try {
      items = (await api.parse(text, source, invoice)).items
    } catch (e) {
      message = `Erro: ${e.message}`
    } finally {
      loading = false
    }
  }

  async function save() {
    const r = await api.saveBulk(items)
    message = `Salvos: ${r.inserted} · duplicados ignorados: ${r.skipped}`
    items = []
    text = ''
    onsaved?.(invoice)
  }

  const prompt = $derived(bankPrompt(invoice.split('-').reverse().join('/')))

  async function copyPrompt() {
    await navigator.clipboard.writeText(prompt)
    message = 'Prompt copiado: cole no assistente do banco e traga a resposta para cá'
  }

  async function copy() {
    await navigator.clipboard.writeText(toTSV(items))
    message = 'Copiado para a área de transferência'
  }
</script>

<details class="prompt">
  <summary>Prompt para o assistente do banco (PicPay AI)</summary>
  <p class="muted">
    Copie, cole no chat do app do banco, e traga a resposta para a caixa abaixo. A última linha
    (TOTAL) ajuda a conferir se nada ficou de fora.
  </p>
  <pre>{prompt}</pre>
  <button class="ghost" onclick={copyPrompt}>Copiar prompt</button>
</details>

<section>
  <div class="row">
    <label>Fonte <input bind:value={source} list="sources" /></label>
    <datalist id="sources"><option>PicPay</option><option>Nubank</option></datalist>
    <label>Fatura <input type="month" bind:value={invoice} /></label>
  </div>
  <textarea bind:value={text} rows="10" placeholder="Cole aqui o texto da fatura..."></textarea>
  <div class="row">
    <button onclick={categorize} disabled={loading || !text.trim() || !source || !invoice}>
      {loading ? 'Categorizando…' : 'Categorizar'}
    </button>
    {#if message}<span class="muted">{message}</span>{/if}
  </div>
</section>

{#if items.length}
  <section>
    <div class="row spread">
      <strong>{items.length} lançamentos · {money(total)}</strong>
      <div class="row">
        <button class="ghost" onclick={copy}>Copiar TSV</button>
        <button onclick={save}>Salvar</button>
      </div>
    </div>
    <TransactionTable
      {items}
      {categories}
      onchange={(item, c) => {
        item.category = c
        item.category_source = 'manual'
      }}
      onnote={(item, note) => (item.note = note || null)}
      onremove={(item) => (items = items.filter((t) => t !== item))}
    />
  </section>
{/if}
