<script>
  import Financitos from './apps/financitos/Financitos.svelte'
  import Tarot from './apps/tarot/Tarot.svelte'
  import Home from './home/Home.svelte'
  import { route } from './lib/router.svelte.js'

  // primeiro segmento do path decide o app: /financitos/... -> financitos
  const pages = { financitos: Financitos, tarot: Tarot }
  const titles = { financitos: '💸 financitos', tarot: '🔮 tarot' }

  let app = $derived(route.path.split('/')[1])
  let Page = $derived(pages[app] ?? Home)

  $effect(() => {
    document.title = titles[app] ?? '⌂ home'
  })
</script>

<Page />
