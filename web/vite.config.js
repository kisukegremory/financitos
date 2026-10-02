import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: ['.localhost'], // acessado via Traefik (dev.home.localhost)
    proxy: {
      // no compose, a API é o serviço "api"; fora dele, ajuste API_TARGET
      '/api': process.env.API_TARGET ?? 'http://api:8000',
    },
  },
})
