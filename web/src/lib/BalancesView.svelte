<script>
  import { api } from './api.js'
  import { dateBR, money, moneyInput, parseMoney } from './format.js'

  let balances = $state([])
  let message = $state('')

  const total = $derived(balances.reduce((s, b) => s + Number(b.amount), 0))

  api.balances().then((b) => (balances = b))

  async function save(balance, raw) {
    const amount = parseMoney(raw)
    if (amount === null) {
      message = `Valor inválido para ${balance.category}: "${raw}"`
      return
    }
    if (amount === Number(balance.amount).toFixed(2)) return
    const updated = await api.setBalance(balance.category, amount)
    Object.assign(balance, updated)
    message = `${balance.category} atualizado: ${money(updated.amount)}`
  }
</script>

<section>
  <div class="row spread">
    <strong>Saldo atual das caixinhas · {money(total)}</strong>
    {#if message}<span class="muted">{message}</span>{/if}
  </div>
  <p class="muted">Edite o valor e aperte Enter (ou saia do campo) para salvar.</p>
</section>

<section class="cards">
  {#each balances as b (b.category)}
    <label class="card balance">
      <span class="muted">{b.category}</span>
      <span class="money-input">
        R$
        <input
          inputmode="decimal"
          value={moneyInput(b.amount)}
          onchange={(e) => save(b, e.currentTarget.value)}
          onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          onfocus={(e) => e.currentTarget.select()}
        />
      </span>
      <small>
        {b.updated_at ? `atualizado em ${dateBR(b.updated_at.slice(0, 10))}` : 'nunca informado'}
      </small>
    </label>
  {/each}
</section>
