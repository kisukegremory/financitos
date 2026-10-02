<script>
  import { api } from './api.js'
  import TarotCard from './TarotCard.svelte'

  let draw = $state(null)
  let error = $state('')

  async function pull() {
    error = ''
    try {
      draw = await api.draw()
    } catch (e) {
      error = e.message
    }
  }
</script>

<section class="center">
  <button onclick={pull}>{draw ? 'Tirar outra carta' : 'Tirar uma carta'}</button>
  {#if error}<p class="error">{error}</p>{/if}
  {#if draw}
    {#key draw}
      <div class="drawn"><TarotCard {draw} reveal /></div>
    {/key}
  {/if}
</section>

<style>
  .center { display: flex; flex-direction: column; align-items: center; gap: 1rem; }
  .drawn { max-width: 480px; animation: appear 0.5s ease-out; }
  @keyframes appear { from { opacity: 0; transform: translateY(12px); } }
  .error { color: var(--danger); }
</style>
