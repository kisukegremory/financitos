# Contrato do catálogo do medichan

Fronteira entre o **estúdio** (gera e publica, no hub) e o **consumo** (aba "Ouvir" hoje;
site/app próprio no futuro). Quem consome só precisa deste arquivo e dos áudios ao lado dele.

## Layout

```
catalog.json
<slug>/audio.ogg   # Opus 64 kbps (principal)
<slug>/audio.m4a   # AAC 96 kbps (fallback e áudio privado)
```

Hoje fica em `data/medichan/public/` (fora do git) e é servido em `/api/medichan/public/`.
Trocar por bucket/CDN = outro `Storage` em `src/home/apps/medichan/publish.py`.

## catalog.json (schema_version 1)

```json
{
  "schema_version": 1,
  "updated_at": "2026-11-12T18:00:00Z",
  "items": [
    {
      "slug": "antes-de-decidir",
      "title": "Antes de decidir",
      "summary": "Para decidir com calma",
      "tags": ["ansiedade"],
      "access": "free",
      "duration_s": 312.4,
      "audio": { "ogg": "antes-de-decidir/audio.ogg", "m4a": "antes-de-decidir/audio.m4a" },
      "published_at": "2026-11-12T18:00:00Z"
    }
  ]
}
```

- `audio.*` são **relativos ao catálogo**.
- `access`: `free` (áudio aberto) | `private` (áudio exige credencial; hoje o token do hub,
  no futuro o usuário assinante). Itens privados aparecem no catálogo para exibir o cadeado.
- Ordem: mais recentes primeiro.
- Campo novo e opcional não muda a versão; remover/renomear campo sobe `schema_version`.

## Áudio

Arquivo único já mixado: voz + pausas + trilha opcional (com ducking), normalizado em
-18 LUFS. Tempos iguais ao player do estúdio: 6 s de entrada, 1,2 s entre falas, 10 s de saída.
