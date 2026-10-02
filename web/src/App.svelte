<script>
  import { api } from './lib/api.js'
  import { currentMonth } from './lib/format.js'
  import ImportView from './lib/ImportView.svelte'
  import InvoiceView from './lib/InvoiceView.svelte'

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
  <h1>💸 financitos</h1>
  <nav>
    <button class:active={tab === 'invoice'} onclick={() => (tab = 'invoice')}>Fatura</button>
    <button class:active={tab === 'import'} onclick={() => (tab = 'import')}>Importar</button>
  </nav>
</header>

<main>
  {#if tab === 'import'}
    <ImportView {categories} {onsaved} />
  {:else}
    <InvoiceView {categories} bind:invoice />
  {/if}
</main>
