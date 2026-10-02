<script>
  // reveal: começa de costas e vira (leitura nova); sem reveal, já aparece de frente
  let { draw, reveal = false, compact = false } = $props()
  let card = $derived(draw.card)
  let flipped = $state(!reveal)

  const suits = { wands: 'Paus · fogo', cups: 'Copas · água', swords: 'Espadas · ar', pentacles: 'Ouros · terra' }
  const roman = ['0', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX', 'XXI']
  let label = $derived(card.arcana === 'major' ? `Arcano maior · ${roman[card.number]}` : suits[card.suit])

  $effect(() => {
    if (!reveal) return
    const t = setTimeout(() => (flipped = true), 350)
    return () => clearTimeout(t)
  })
</script>

<div class="tarot-card" class:compact>
  <div class="stage">
    <div class="flipper" class:flipped>
      <div class="face back" aria-hidden="true">
        <span>✦</span>
      </div>
      <div class="face front">
        <img src={`/tarot/${card.id}.webp`} alt={card.name} class:reversed={draw.reversed} />
      </div>
    </div>
  </div>

  <div class="info" class:shown={flipped}>
    <span class="label">{label}</span>
    <h3>{card.name}</h3>
    <span class="orientation" class:inv={draw.reversed}>{draw.reversed ? '↓ invertida' : '↑ normal'}</span>
    <div class="keywords">
      {#each card.keywords as k (k)}<span>{k}</span>{/each}
    </div>
    {#if !compact}
      <p>{draw.reversed ? card.reversed : card.upright}</p>
    {/if}
  </div>
</div>

<style>
  .tarot-card { display: flex; flex-direction: column; align-items: center; text-align: center; }
  .stage { perspective: 1200px; width: 100%; max-width: 250px; }
  .compact .stage { max-width: 150px; }
  .flipper {
    position: relative; aspect-ratio: 360 / 620;
    transform-style: preserve-3d; transition: transform 0.9s cubic-bezier(0.2, 0.7, 0.2, 1);
  }
  .flipper.flipped { transform: rotateY(180deg); }
  .face {
    position: absolute; inset: 0; backface-visibility: hidden; border-radius: 14px; overflow: hidden;
    box-shadow: 0 10px 40px rgba(180, 140, 255, 0.3), 0 0 0 1px rgba(180, 140, 255, 0.35);
  }
  .front { transform: rotateY(180deg); background: #f4ecd8; }
  .back {
    display: grid; place-items: center; color: #e9d8ff; font-size: 3rem;
    background:
      radial-gradient(circle at 50% 50%, rgba(255, 215, 140, 0.25), transparent 45%),
      repeating-linear-gradient(45deg, #2a1650 0 10px, #321c5e 10px 20px);
    border: 6px solid #1a0d33;
  }
  img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.6s; }
  img.reversed { transform: rotate(180deg); }

  .info { opacity: 0; transform: translateY(8px); transition: opacity 0.5s 0.5s, transform 0.5s 0.5s; }
  .info.shown { opacity: 1; transform: none; }
  .label { display: block; margin-top: 1rem; font-size: 0.72rem; letter-spacing: 0.15em; text-transform: uppercase; color: var(--muted); }
  h3 { font-family: Georgia, 'Times New Roman', serif; font-size: 1.5rem; font-weight: 400; margin: 0.2rem 0; color: #f3e9ff; }
  .compact h3 { font-size: 1.1rem; }
  .orientation { font-size: 0.8rem; color: var(--accent); }
  .orientation.inv { color: #ffb38a; }
  .keywords { display: flex; flex-wrap: wrap; gap: 0.35rem; justify-content: center; margin: 0.75rem 0; }
  .keywords span {
    border: 1px solid rgba(180, 140, 255, 0.5); color: var(--accent);
    border-radius: 999px; padding: 0.1rem 0.6rem; font-size: 0.78rem;
  }
  p { line-height: 1.6; color: var(--muted); margin: 0; }
</style>
