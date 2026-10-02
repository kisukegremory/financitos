// Prompt para colar no assistente do banco (ex.: PicPay AI) e obter a fatura
// num texto limpo, que o financitos categoriza com mais precisão.
export const bankPrompt = (invoice) => `Liste TODOS os lançamentos da fatura do meu cartão de crédito com vencimento em ${invoice || '[mês/ano]'}.

Regras:
- Uma linha por lançamento, no formato exato: DD/MM/AAAA;VALOR;DESCRIÇÃO
- VALOR com vírgula decimal e sem "R$" (ex.: 1234,56). Estornos e créditos com sinal negativo (ex.: -19,90).
- DESCRIÇÃO exatamente como aparece na fatura, sem resumir nem traduzir.
- Compras parceladas: inclua só a parcela desta fatura e coloque "Parcela X/Y" no fim da descrição.
- Inclua compras de todos os cartões (físico, virtual e adicionais), assinaturas, IOF e tarifas.
- NÃO inclua pagamento da fatura anterior, saldo, limite nem o total.
- Não agrupe lançamentos iguais: se houver duas compras idênticas, liste as duas.
- Na última linha, escreva: TOTAL;VALOR_TOTAL_DA_FATURA
- Responda apenas com as linhas, sem texto antes ou depois e sem tabela.`
