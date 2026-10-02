# PRD — financitos

> Status: rascunho v0.1 · Autor: Gustavo · Data: 2026-10-01

## 1. Problema

Todo mês preciso pagar a fatura do cartão distribuindo o valor entre minhas caixinhas do PicPay. Para isso, cada lançamento precisa ser atribuído a uma caixinha. Hoje o processo é manual: exportar a fatura, pedir para uma LLM no chat formatar, copiar e colar numa planilha. É lento, propenso a erro e não guarda histórico estruturado.

## 2. Objetivos

- Converter o texto bruto de uma fatura em lançamentos estruturados no formato da planilha.
- Categorizar automaticamente cada lançamento em uma caixinha válida.
- Identificar a fonte (cartão) e o mês da fatura.
- Ter custo de LLM irrisório (centavos por fatura).
- Evoluir incrementalmente: CLI → SQLite → API → UI, num único repositório.
- Rodar em Docker numa VPS com acesso privado.

### Não-objetivos (por agora)

- Multiusuário, autenticação complexa, exposição pública.
- Integração direta com bancos (Open Finance, scraping).
- Contabilidade completa / orçamento detalhado.

## 3. Persona

Uso exclusivamente pessoal (eu). Técnico, confortável com terminal, quer o mínimo de atrito no fechamento mensal da fatura.

## 4. Caixinhas (categorias válidas)

`Viagem`, `Pessoal`, `Mercado`, `Buffer Anual`, `Buffer Mensal`, `Estudo`, `Casa`, `Saúde`, `Contas e assinaturas`, `Higiene e Estética`.

A LLM **só** pode retornar valores dessa lista (validado no código). Lista centralizada em um único módulo para facilitar mudanças.

## 5. Modelo de dados

| Campo | Tipo | Regra |
|---|---|---|
| `date` (Data) | `date` (ISO 8601, `AAAA-MM-DD`) | Data da compra; armazenada em formato nativo, formatada como `DD/MM/AAAA` só na saída |
| `amount` (Gasto) | decimal (2 casas) | Positivo = gasto; negativo = estorno/crédito |
| `category` (Caixinha) | enum | Uma das caixinhas |
| `description` (Descrição) | texto | Texto original do cartão, sem alterações |
| `source` (Fonte) | texto | `PicPay`, `Nubank`, ... |
| `invoice` (Fatura) | `date` (1º dia do mês) | Mês de referência da fatura; exibido como `AAAA-MM` |

Campos internos previstos para o SQLite: `id`, `created_at`/`updated_at` (`datetime` UTC, ISO 8601), `category_source` (`llm` / `manual`) e `raw_line` (linha original, para auditoria).

## 6. Requisitos funcionais por fase

### Fase 1 — CLI

- **RF1.1** Receber o texto da fatura por arquivo ou stdin.
- **RF1.2** Receber `--source` (cartão) e `--invoice` (mês). Se omitidos, tentar inferir e, se não der, perguntar.
- **RF1.3** Enviar o texto à LLM via OpenRouter e obter JSON estruturado (lista de lançamentos).
- **RF1.4** Validar a resposta (Pydantic). Lançamentos inválidos são reportados, não descartados em silêncio.
- **RF1.5** Datas tratadas internamente como `date`; formatação `DD/MM/AAAA` e valor com vírgula só na camada de saída.
- **RF1.6** Saída em TSV (padrão, cola direto na planilha) ou CSV (`--format csv`).
- **RF1.7** Mostrar o total, para conferir com o valor da fatura.
- **RF1.8** Configuração via `.env` (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, ...).

### Fase 2 — SQLite

- **RF2.1** `financitos save`: persistir os lançamentos processados.
- **RF2.2** `financitos list --invoice 2026-10 [--category X]`: consultar.
- **RF2.3** Totais por caixinha de uma fatura (o valor a transferir de cada caixinha).
- **RF2.4** Evitar duplicatas (mesma data + valor + descrição + fonte + fatura).

### Fase 3 — API

- **RF3.1** FastAPI com `GET/POST/PUT/DELETE /transactions` e `POST /parse`.
- **RF3.2** `GET /invoices/{yyyy-mm}/summary` com totais por caixinha.
- **RF3.3** Mesma camada de domínio do CLI (sem duplicar lógica).

### Fase 4 — UI

- **RF4.1** Colar texto da fatura → revisar/editar categorias → salvar.
- **RF4.2** Visualizar a fatura do mês e os totais por caixinha.
- Framework JS leve (ex.: SvelteKit ou React + Vite), servido pelo mesmo compose.

## 7. Requisitos não funcionais

- **Custo**: modelo barato por padrão (`deepseek/deepseek-chat`); `xiaomi/mimo` como alternativa/reserva; modelo trocável via env.
- **Privacidade**: dados financeiros ficam na minha VPS; só o texto da fatura vai para o provedor de LLM. Sem telemetria.
- **Confiabilidade**: saída da LLM sempre validada; temperatura baixa; retry com o modelo reserva.
- **Deploy**: imagem Docker multi-stage, slim, sem root; `compose.yaml` com volume para `data/`; acesso à VPS só por rede privada (ex.: Tailscale/WireGuard).
- **Manutenção**: monorepo, testes com LLM mockada, lint com ruff.

## 8. Evoluções (fora de escopo)

- Armazenar os saldos das caixinhas.
- Aceitar imagem (print/foto da fatura) como entrada, usando um modelo com visão.
- Contas a pagar e controle de quando foram pagas.
- Gestão do Buffer Anual.
- Categorizar automaticamente pelo histórico (mesma descrição → mesma caixinha, sem chamar a LLM).
- Interação via Telegram (bot).

## 9. Métricas de sucesso

- Fechar a fatura do mês em **< 5 minutos**.
- **≥ 90%** dos lançamentos categorizados corretamente sem edição.
- Custo de LLM **< US$ 0,05** por fatura.
- Total calculado bate com o valor da fatura.

## 10. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| LLM inventa/omite lançamentos | Mostrar total e contagem; guardar a linha original; comparar com a fatura |
| Categoria fora da lista | Enum validado; retry; marcar como pendente |
| Formatos de fatura diferentes por banco | Prompt com exemplos por fonte; fixtures de teste por banco |
| Modelo barato sai do ar ou muda | Modelo configurável + reserva |
| Vazamento da chave | `.env` fora do git e da imagem Docker (`.dockerignore`) |
