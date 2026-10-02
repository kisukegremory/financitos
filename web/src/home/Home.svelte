<script>
  import { apps } from '../apps.js'
  import { link } from '../lib/router.svelte.js'
</script>

<header>
  <h1>⌂ home</h1>
</header>

<main>
  <div class="apps">
    {#each apps as app (app.path)}
      <a class="app" href={app.path} onclick={link}>
        <span class="icon">{app.icon}</span>
        <strong>{app.name}</strong>
        <span class="muted">{app.description}</span>
      </a>
    {/each}
  </div>
</main>

<style>
  .apps { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
  .app {
    display: flex; flex-direction: column; gap: 0.4rem;
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.25rem; color: var(--text); text-decoration: none;
  }
  .app:hover { border-color: var(--accent); }
  .icon { font-size: 2rem; }
</style>
