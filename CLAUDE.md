# home (financitos + tarot + medichan)

## Depois de cada mudança
- Ao terminar qualquer novidade (backend ou UI), reconstruir e reiniciar o compose do hub:
  `docker compose up -d --build api`, e conferir `docker compose ps api` (healthy) + a rota afetada
  em `http://home.localhost`.
- Node não está instalado no host: build/dev da UI pelo compose (perfil `dev` para hot reload).
