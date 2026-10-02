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

// '1.500,00' | '1500,00' | '1500.00' -> '1500.00' (string decimal para a API); null se inválido
export function parseMoney(raw) {
  let v = String(raw).replace(/[R$\s]/g, '')
  if (v.includes(',')) v = v.replace(/\./g, '').replace(',', '.')
  return v !== '' && !Number.isNaN(Number(v)) ? Number(v).toFixed(2) : null
}

// valor para exibir num input editável: '1500.00' -> '1.500,00'
export const moneyInput = (v) =>
  Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
