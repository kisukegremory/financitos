# home

Monolito modular dos meus apps pessoais: um backend FastAPI, um front Svelte, um SQLite e um compose.
A home (`/`) é um seletor de projetos e cada app vive no seu path:

| App | UI | API | Código |
|---|---|---|---|
| 💸 financitos | `/financitos` | `/api/financitos` | `src/home/apps/financitos`, `web/src/apps/financitos` |
| 🔮 tarot | `/tarot` | `/api/tarot` | `src/home/apps/tarot`, `web/src/apps/tarot` |

O que é compartilhado fica em `src/home/core` (config, conexão SQLite, cliente LLM com fallback, token)
e `web/src/lib` (cliente HTTP, roteador, formatação). Cada app registra suas tabelas (com prefixo, ex.: `fin_`)
em `core.db.register`, expõe um `APIRouter` montado em `src/home/main.py` e uma página em `web/src/App.svelte`.

## tarot

Guarda frases que me marcaram, gera novas com a LLM (a partir de um prompt base editável, usando as
favoritas como referência de tom; sugestões só são salvas depois de revisadas) e tira cartas do tarot
Rider-Waite-Smith com significado normal/invertido em português (`src/home/apps/tarot/cards.json`).
O gerador tem três modos: **Original** (tom do prompt base), **Citação real** (frases conhecidas de um
pensador, com autor e obra; a IA pode errar atribuições, então confira) e **Inspirada em** (frases novas no
estilo de alguém). **Sugerir pensadores** recomenda nomes e obras para um tema; clicar escolhe o pensador.

Na aba **Hoje**, você escreve como está e, em paralelo, a LLM (1) escolhe um pensador que conversa com o
momento e traz 3 citações reais dele, que podem ser guardadas com um clique, e (2) escolhe da sua coleção a
frase que encaixa (ou sugere uma nova) e explica a relação. A carta sorteada vira na tela e é interpretada
no seu contexto; as leituras ficam no histórico.
As imagens ficam em `web/public/tarot/` e podem ser rebaixadas com
`uv run --with pillow --with httpx scripts/fetch_tarot_images.py`.

## financitos

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

Abra **http://home.localhost/financitos** (UI). A API fica em `/api/financitos` e a documentação interativa em `/docs`.
Telas: **Fatura** (devido/pago/falta por caixinha, pagar o que falta, saldo após pagar, editar caixinha e comentário, copiar TSV),
**Importar** (prompt para o assistente do banco → colar fatura → categorizar → revisar → salvar) e
**Caixinhas** (saldo atual de cada uma).

O Traefik é a porta de entrada (porta 80, só na sua máquina) e encaminha para o container da app.
`*.localhost` já aponta para a própria máquina nos navegadores, então não precisa mexer em `/etc/hosts`.

```bash
docker compose logs -f api   # logs
docker compose down          # parar
```

### Pelo terminal (CLI)

```bash
uv sync
uv run home financitos parse -s PicPay -i 2026-10 data/fatura.txt          # só mostra (TSV)
uv run home financitos parse -s PicPay -i 2026-10 data/fatura.txt --save   # mostra e salva
uv run home financitos list -i 2026-10 [-s PicPay] [-c Mercado]
uv run home financitos summary -i 2026-10                                  # devido × pago × falta por caixinha
uv run home financitos pay -s PicPay -i 2026-10 [-d 2026-10-02]             # paga o que falta (vale antecipado)
uv run home financitos balances [--set Mercado 1.500,00]                    # saldo das caixinhas
```

Também funciona via Docker: `docker compose run --rm -T cli financitos parse -s PicPay -i 2026-10 --save < data/fatura.txt`.

> Guarde as faturas em `data/` ou `inbox/`; as duas pastas (e `*.txt`) são ignoradas pelo git.

### Desenvolvendo a UI (hot reload, sem Node instalado)

```bash
docker compose --profile dev up -d
```

Abra **http://dev.home.localhost**: a UI recarrega a cada alteração em `web/` e usa a mesma API.

### Rotas da API

| Método | Rota | O quê |
|---|---|---|
| GET | `/api/health` | Status (sem token) |
| GET | `/api/financitos/categories` | Lista de caixinhas |
| POST | `/api/financitos/parse` | `{text, source, invoice, save}` → lançamentos categorizados |
| GET | `/api/financitos/transactions?invoice=&source=&category=` | Lista |
| POST | `/api/financitos/transactions` | Cria manualmente |
| POST | `/api/financitos/transactions/bulk` | Salva vários (ignora duplicatas) |
| GET/PUT/DELETE | `/api/financitos/transactions/{id}` | Lê / edita (mudar caixinha marca `manual`) / remove |
| GET | `/api/financitos/invoices/{AAAA-MM}/summary` | Devido × pago × falta por caixinha |
| POST | `/api/financitos/invoices/{AAAA-MM}/pay` | `{source, paid_at}` → paga o que falta em cada caixinha |
| GET/POST | `/api/financitos/payments` | Lista / registra um pagamento avulso (caixinha + valor) |
| DELETE | `/api/financitos/payments/{id}` | Desfaz um pagamento |
| GET | `/api/financitos/balances` | Saldo atual de cada caixinha |
| PUT | `/api/financitos/balances/{caixinha}` | `{amount}` → atualiza o saldo |

Se `API_TOKEN` estiver definido no `.env`, todas as rotas (exceto `/api/health`) exigem `Authorization: Bearer <token>`.
Datas trafegam em ISO (`2026-09-15`), valores como string decimal (`"42.90"`).

O endereço antigo `financitos.localhost` redireciona para `home.localhost/financitos`.

### Na VPS (futuro)

Defina `APP_HOST` no `.env` com o nome que você usa na VPN/Tailscale (ex.: `home.minha-tailnet.ts.net`)
e ajuste a porta publicada do Traefik para a interface privada. TLS pode ser ligado no próprio Traefik.

## Convenções de desenvolvimento

- Histórico **linear** direto na `main` (por enquanto sem branches).
- Toda mudança é **revisada antes do commit**; após aprovação → commit + push.
- Mensagens no padrão [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`...).
- Docs em português; código e identificadores em inglês.
- Segredos só no `.env` (nunca versionado); `.env.example` documenta as variáveis.
