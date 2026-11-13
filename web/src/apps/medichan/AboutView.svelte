<script>
  // "Sobre mim": contexto pessoal que entra no prompt do roteiro + limite de retenção do ar.
  import { api } from './api.js'

  const PROMPTS = [
    'Quem sou eu hoje (idade, onde moro, com quem vivo)',
    'Trabalho, rotina e o que ocupa minha cabeça',
    'Pessoas, lugares e coisas que me fazem bem',
    'O que estou atravessando ou tentando mudar',
    'Crenças ou palavras que prefiro que evite',
  ]

  let about = $state('')
  let maxHold = $state(3)
  let saved = $state(null) // último estado salvo, para saber se há mudanças
  let busy = $state(false)
  let error = $state('')
  let status = $state('')

  api.profile().then((p) => {
    about = p.about
    maxHold = p.max_hold
    saved = p
  }).catch((e) => (error = e.message))

  let dirty = $derived(saved && (about !== saved.about || maxHold !== saved.max_hold))

  async function save() {
    busy = true
    error = ''
    try {
      saved = await api.saveProfile({ about, max_hold: maxHold })
      status = 'guardado ✓'
      setTimeout(() => (status = ''), 2500)
    } catch (e) {
      error = e.message
    } finally {
      busy = false
    }
  }

  const holdLabel = (s) => (s === 0 ? 'sem prender o ar' : `até ${s} s`)
</script>

<section>
  <h2>Sobre mim</h2>
  <p class="muted lead">
    O que você escrever aqui entra em todas as meditações novas, para que imagens, exemplos e
    perguntas falem da sua vida. Fica só no seu servidor.
  </p>

  <div class="chips">
    {#each PROMPTS as p (p)}
      <span class="hint">{p}</span>
    {/each}
  </div>

  <textarea
    rows="12"
    maxlength="6000"
    placeholder="Ex.: tenho 30 anos, trabalho com tecnologia e passo o dia no computador. Moro com minha companheira e duas gatas. Ando ansioso com uma mudança de emprego. Me acalma: mar, chuva, cozinhar..."
    bind:value={about}
  ></textarea>
  <p class="muted count">{about.length} / 6000</p>
</section>

<section>
  <h2>Respiração</h2>
  <p class="muted lead">
    Os exercícios usam tempos fixos de técnicas conhecidas (ressonante 5·5, expiração alongada 4·6,
    suspiro cíclico, quadrada suave). Aqui você limita quanto tempo as meditações pedem para segurar
    o ar.
  </p>
  <label class="hold">
    <span>Segurar a respiração: <strong>{holdLabel(maxHold)}</strong></span>
    <input type="range" min="0" max="7" step="1" bind:value={maxHold} />
  </label>
  <p class="muted small">
    Retenção deve ser confortável: se sentir tontura ou falta de ar, volte a respirar normalmente.
    Com pressão alta ou questões cardíacas, prefira “sem prender o ar”.
  </p>
</section>

<div class="actions">
  {#if error}<span class="error">{error}</span>{/if}
  {#if status}<span class="ok">{status}</span>{/if}
  <button disabled={!dirty || busy} onclick={save}>{busy ? 'guardando…' : 'guardar'}</button>
</div>

<style>
  .lead { margin: 0 0 0.75rem; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .hint {
    font-size: 0.78rem; padding: 0.25rem 0.75rem; border-radius: 999px;
    border: 1px dashed var(--border); color: var(--muted);
  }
  .count { text-align: right; font-size: 0.75rem; margin: -0.4rem 0 0; }
  .hold { gap: 0.6rem; font-size: 0.95rem; color: var(--text); }
  .hold strong { color: var(--accent); font-weight: 600; }
  .hold input { width: 100%; }
  .small { font-size: 0.8rem; }
  .actions {
    position: sticky; bottom: calc(6rem + env(safe-area-inset-bottom));
    display: flex; justify-content: flex-end; align-items: center; gap: 1rem;
  }
  .actions button { padding: 0.8rem 2.2rem; }
  .ok { color: var(--sage); }
  .error { color: var(--danger); }
  @media (min-width: 721px) { .actions { bottom: 1rem; } }
</style>
