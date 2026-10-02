<script>
  import Financitos from './apps/financitos/Financitos.svelte'
  import Home from './home/Home.svelte'
  import { route } from './lib/router.svelte.js'

  // primeiro segmento do path decide o app: /financitos/... -> financitos
  const pages = { financitos: Financitos }
  const titles = { financitos: '💸 financitos' }

  let app = $derived(route.path.split('/')[1])
  let Page = $derived(pages[app] ?? Home)

  $effect(() => {
    document.title = titles[app] ?? '⌂ home'
  })
</script>

<Page />
