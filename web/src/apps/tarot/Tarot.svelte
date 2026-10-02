<script>
  import { link } from '../../lib/router.svelte.js'
  import CardView from './CardView.svelte'
  import PhrasesView from './PhrasesView.svelte'
  import PromptView from './PromptView.svelte'
  import ReadingView from './ReadingView.svelte'

  let tab = $state('today')
</script>

<div class="tarot">
  <header>
    <h1><a href="/" onclick={link} class="home-link">⌂</a> 🔮 tarot</h1>
    <nav>
      <button class:active={tab === 'today'} onclick={() => (tab = 'today')}>Hoje</button>
      <button class:active={tab === 'phrases'} onclick={() => (tab = 'phrases')}>Frases</button>
      <button class:active={tab === 'card'} onclick={() => (tab = 'card')}>Carta</button>
      <button class:active={tab === 'prompt'} onclick={() => (tab = 'prompt')}>Prompt base</button>
    </nav>
  </header>

  <main>
    {#if tab === 'card'}
      <CardView />
    {:else if tab === 'prompt'}
      <PromptView />
    {:else if tab === 'phrases'}
      <PhrasesView />
    {:else}
      <ReadingView />
    {/if}
  </main>
</div>

<style>
  /* tom místico só dentro do tarot */
  .tarot { --accent: #b48cff; }
</style>
