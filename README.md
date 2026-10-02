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

```bash
cp .env.example .env   # e preencha OPENROUTER_API_KEY
```

### Uso normal: um comando, uma URL

```bash
docker compose up -d --build
```

Abra **http://financitos.localhost** (UI). A API fica em `/api` e a documentação interativa em `/docs`.
O Traefik é a porta de entrada (porta 80, só na sua máquina) e encaminha para o container da app.
`*.localhost` já aponta para a própria máquina nos navegadores, então não precisa mexer em `/etc/hosts`.

```bash
docker compose logs -f api   # logs
docker compose down          # parar
```

### Pelo terminal (CLI)

```bash
uv sync
uv run financitos parse -s PicPay -i 2026-10 data/fatura.txt          # só mostra (TSV)
uv run financitos parse -s PicPay -i 2026-10 data/fatura.txt --save   # mostra e salva
uv run financitos list -i 2026-10 [-s PicPay] [-c Mercado]
uv run financitos summary -i 2026-10                                  # devido × pago × falta por caixinha
uv run financitos pay -s PicPay -i 2026-10 [-d 2026-10-02]             # paga o que falta (vale antecipado)
```

Também funciona via Docker: `docker compose run --rm -T cli parse -s PicPay -i 2026-10 --save < data/fatura.txt`.

> Guarde as faturas em `data/` ou `inbox/`; as duas pastas (e `*.txt`) são ignoradas pelo git.

### Desenvolvendo a UI (hot reload, sem Node instalado)

```bash
docker compose --profile dev up -d
```

Abra **http://dev.financitos.localhost**: a UI recarrega a cada alteração em `web/` e usa a mesma API.

### Rotas da API

| Método | Rota | O quê |
|---|---|---|
| GET | `/api/health` | Status (sem token) |
| GET | `/api/categories` | Lista de caixinhas |
| POST | `/api/parse` | `{text, source, invoice, save}` → lançamentos categorizados |
| GET | `/api/transactions?invoice=&source=&category=` | Lista |
| POST | `/api/transactions` | Cria manualmente |
| POST | `/api/transactions/bulk` | Salva vários (ignora duplicatas) |
| GET/PUT/DELETE | `/api/transactions/{id}` | Lê / edita (mudar caixinha marca `manual`) / remove |
| GET | `/api/invoices/{AAAA-MM}/summary` | Devido × pago × falta por caixinha |
| POST | `/api/invoices/{AAAA-MM}/pay` | `{source, paid_at}` → paga o que falta em cada caixinha |
| GET/POST | `/api/payments` | Lista / registra um pagamento avulso (caixinha + valor) |
| DELETE | `/api/payments/{id}` | Desfaz um pagamento |

Se `API_TOKEN` estiver definido no `.env`, todas as rotas (exceto `/api/health`) exigem `Authorization: Bearer <token>`.
Datas trafegam em ISO (`2026-09-15`), valores como string decimal (`"42.90"`).

### Na VPS (futuro)

Defina `APP_HOST` no `.env` com o nome que você usa na VPN/Tailscale (ex.: `financitos.minha-tailnet.ts.net`)
e ajuste a porta publicada do Traefik para a interface privada. TLS pode ser ligado no próprio Traefik.

## Convenções de desenvolvimento

- Histórico **linear** direto na `main` (por enquanto sem branches).
- Toda mudança é **revisada antes do commit**; após aprovação → commit + push.
- Mensagens no padrão [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`...).
- Docs em português; código e identificadores em inglês.
- Segredos só no `.env` (nunca versionado); `.env.example` documenta as variáveis.
