<script>
  import { api } from './api.js'

  let value = $state('')
  let saved = $state('')
  let status = $state('')

  api.basePrompt().then((p) => (value = saved = p.value))

  async function save() {
    try {
      saved = value = (await api.setBasePrompt(value)).value
      status = 'Salvo.'
    } catch (e) {
      status = e.message
    }
  }
</script>

<section>
  <p class="muted">
    Instruções que a IA segue ao gerar frases. Suas favoritas também vão como referência de tom.
  </p>
  <textarea rows="8" bind:value></textarea>
  <div class="row">
    <button disabled={!value.trim() || value === saved} onclick={save}>Salvar</button>
    <span class="muted">{status}</span>
  </div>
</section>

<style>
  textarea { font-family: inherit; font-size: 0.95rem; }
</style>
