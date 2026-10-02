const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export const money = (v) => brl.format(Number(v))

// '2026-09-15' -> '15/09/2026' (sem passar por Date, evitando fuso)
export const dateBR = (iso) => iso.split('-').reverse().join('/')

// '2026-10-01' -> '2026-10'
export const month = (iso) => iso.slice(0, 7)

export const currentMonth = () => new Date().toISOString().slice(0, 7)

// Mesmo formato do CLI: cola direto na planilha
export function toTSV(items) {
  const header = ['Data', 'Gasto', 'Caixinha', 'Descrição', 'Fonte', 'Fatura']
  const rows = items.map((t) => [
    dateBR(t.date),
    Number(t.amount).toFixed(2).replace('.', ','),
    t.category,
    t.description,
    t.source,
    month(t.invoice),
  ])
  return [header, ...rows].map((r) => r.join('\t')).join('\n')
}
