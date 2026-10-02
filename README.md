# financitos

Ferramenta pessoal para transformar a fatura do cartão em linhas prontas para a planilha, já **categorizadas nas minhas caixinhas do PicPay**, usando uma LLM via [OpenRouter](https://openrouter.ai).

## Motivação

No Nubank eu exportava a fatura em CSV, mandava pro Gemini formatar, e colava o resultado numa planilha. Funcionava, mas era manual, repetitivo e dependia de prompt na mão. O `financitos` automatiza esse fluxo: recebe o texto da fatura (de qualquer cartão), normaliza, categoriza e devolve/armazena no formato da planilha.

## Caixinhas

| Caixinha |
|---|
| Viagem |
| Pessoal |
| Mercado |
| Buffer Anual |
| Buffer Mensal |
| Estudo |
| Casa |
| Saúde |
| Contas e assinaturas |
| Higiene e Estética |

## Formato de saída

| Coluna | Descrição | Exemplo |
|---|---|---|
| Data | Data da compra (armazenada como `date` ISO, exibida `DD/MM/AAAA`) | `15/09/2026` |
| Gasto | Valor em reais | `42,90` |
| Caixinha | Atribuída pela LLM (uma das caixinhas acima) | `Mercado` |
| Descrição | Texto original do cartão | `SUPERMERCADO XPTO` |
| Fonte | Cartão/banco de origem | `PicPay`, `Nubank` |
| Fatura | Mês de referência da fatura (`AAAA-MM`) | `2026-10` |

## Stack

- **Python 3.12+** com [uv](https://docs.astral.sh/uv/)
- **CLI**: Typer
- **LLM**: SDK `openai` apontando para o OpenRouter (modelo padrão `deepseek/deepseek-chat`, Xiaomi MiMo como reserva)
- **Validação**: Pydantic
- **Armazenamento**: SQLite
- **API** (fase 2): FastAPI
- **UI** (fase 3): framework JS leve (a definir)
- **Deploy**: Docker multi-stage + Docker Compose em VPS privada

## Roadmap

1. **CLI** — texto da fatura → CSV/TSV categorizado
2. **SQLite** — persistir lançamentos
3. **API** — CRUD de lançamentos (GET/POST/PUT)
4. **UI** — interface web básica
5. **Evoluções** (fora do escopo próximo) — ver [PRD](docs/PRD.md#evoluções-fora-de-escopo)

Detalhes em [`docs/PRD.md`](docs/PRD.md).

## Como rodar

### Configuração

```bash
cp .env.example .env   # e preencha OPENROUTER_API_KEY
```

### Local (uv)

```bash
uv sync
uv run financitos parse --source picpay --invoice 2026-10 data/fatura.txt
# ou via stdin (ex.: área de transferência no Linux)
xclip -o -sel clip | uv run financitos parse --source nubank --invoice 2026-10

# salvar no SQLite (reimportar a mesma fatura não duplica)
uv run financitos parse -s PicPay -i 2026-10 data/fatura.txt --save

# consultar
uv run financitos list -i 2026-10 [-s PicPay] [-c Mercado]
uv run financitos summary -i 2026-10   # total por caixinha
```

> Guarde as faturas em `data/` ou `inbox/` — ambos (e `*.txt`) são ignorados pelo git.

### Docker

```bash
# API (fica em 127.0.0.1:8000)
docker compose up -d api

# CLI sob demanda
docker compose run --rm -T cli parse -s PicPay -i 2026-10 --save < data/fatura.txt
docker compose run --rm cli summary -i 2026-10
```

### API

```bash
uv run financitos serve --reload   # dev local; docs em http://127.0.0.1:8000/docs
```

| Método | Rota | O quê |
|---|---|---|
| GET | `/health` | Status (sem token) |
| GET | `/categories` | Lista de caixinhas |
| POST | `/parse` | `{text, source, invoice, save}` → lançamentos categorizados |
| GET | `/transactions?invoice=&source=&category=` | Lista |
| POST | `/transactions` | Cria manualmente |
| GET/PUT/DELETE | `/transactions/{id}` | Lê / edita (mudar caixinha marca `manual`) / remove |
| GET | `/invoices/{AAAA-MM}/summary` | Total por caixinha |

Se `API_TOKEN` estiver definido no `.env`, todas as rotas (exceto `/health`) exigem `Authorization: Bearer <token>`.
Datas trafegam em ISO (`2026-09-15`), valores como string decimal (`"42.90"`).

## Convenções de desenvolvimento

- Histórico **linear** direto na `main` (por enquanto sem branches).
- Toda mudança é **revisada antes do commit**; após aprovação → commit + push.
- Mensagens no padrão [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`...).
- Docs em português; código e identificadores em inglês.
- Segredos só no `.env` (nunca versionado); `.env.example` documenta as variáveis.
