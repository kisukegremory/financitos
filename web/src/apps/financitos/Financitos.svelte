<script>
  import { link } from '../../lib/router.svelte.js'
  import { api } from './api.js'
  import { currentMonth } from '../../lib/format.js'
  import BalancesView from './BalancesView.svelte'
  import ImportView from './ImportView.svelte'
  import InvoiceView from './InvoiceView.svelte'

  let tab = $state('invoice')
  let invoice = $state(currentMonth())
  let categories = $state([])

  api.categories().then((c) => (categories = c))

  function onsaved(savedInvoice) {
    invoice = savedInvoice
    tab = 'invoice'
  }
</script>

<header>
  <h1><a href="/" onclick={link} class="home-link">⌂</a> 💸 financitos</h1>
  <nav>
    <button class:active={tab === 'invoice'} onclick={() => (tab = 'invoice')}>Fatura</button>
    <button class:active={tab === 'import'} onclick={() => (tab = 'import')}>Importar</button>
    <button class:active={tab === 'balances'} onclick={() => (tab = 'balances')}>Caixinhas</button>
  </nav>
</header>

<main>
  {#if tab === 'import'}
    <ImportView {categories} {onsaved} />
  {:else if tab === 'balances'}
    <BalancesView />
  {:else}
    <InvoiceView {categories} bind:invoice />
  {/if}
</main>
