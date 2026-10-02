<script>
  let { draw } = $props()
  let card = $derived(draw.card)
</script>

<figure class="card-face">
  <img src={`/tarot/${card.id}.webp`} alt={card.name} class:reversed={draw.reversed} />
  <figcaption>
    <strong>{card.name}</strong>
    <span class="muted">{draw.reversed ? 'invertida' : 'normal'}</span>
  </figcaption>
</figure>
<div class="keywords">
  {#each card.keywords as k (k)}<span>{k}</span>{/each}
</div>
<p>{draw.reversed ? card.reversed : card.upright}</p>

<style>
  .card-face { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
  img {
    width: 100%; max-width: 260px; border-radius: 12px;
    box-shadow: 0 8px 30px rgba(180, 140, 255, 0.25); transition: transform 0.6s;
  }
  img.reversed { transform: rotate(180deg); }
  figcaption { display: flex; flex-direction: column; align-items: center; }
  figcaption strong { font-size: 1.2rem; }
  .keywords { display: flex; flex-wrap: wrap; gap: 0.4rem; justify-content: center; margin: 0.75rem 0; }
  .keywords span {
    border: 1px solid var(--accent); color: var(--accent);
    border-radius: 999px; padding: 0.1rem 0.6rem; font-size: 0.8rem;
  }
  p { line-height: 1.6; text-align: center; }
</style>
