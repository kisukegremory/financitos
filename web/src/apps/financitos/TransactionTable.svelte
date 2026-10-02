<script>
  import { dateBR, money } from '../../lib/format.js'

  /** @type {{ items: any[], categories: string[], onchange?: (item: any, category: string) => void, onnote?: (item: any, note: string) => void, onremove?: (item: any) => void }} */
  let { items, categories, onchange, onnote, onremove } = $props()

  function commitNote(item, value) {
    if (value.trim() !== (item.note ?? '')) onnote?.(item, value.trim())
  }
</script>

<table>
  <thead>
    <tr>
      <th>Data</th>
      <th class="num">Gasto</th>
      <th>Caixinha</th>
      <th>Descrição</th>
      <th>Fonte</th>
      <th>Comentário</th>
      {#if onremove}<th></th>{/if}
    </tr>
  </thead>
  <tbody>
    {#each items as item, i (item.id ?? i)}
      <tr class:manual={item.category_source === 'manual'}>
        <td>{dateBR(item.date)}</td>
        <td class="num" class:negative={Number(item.amount) < 0}>{money(item.amount)}</td>
        <td>
          <select value={item.category} onchange={(e) => onchange?.(item, e.currentTarget.value)}>
            {#each categories as c}<option>{c}</option>{/each}
          </select>
        </td>
        <td>{item.description}</td>
        <td>{item.source}</td>
        <td>
          <input
            class="note"
            value={item.note ?? ''}
            placeholder="—"
            title={item.note ?? 'Adicionar comentário'}
            onchange={(e) => commitNote(item, e.currentTarget.value)}
            onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          />
        </td>
        {#if onremove}
          <td><button class="ghost" title="Remover" onclick={() => onremove(item)}>✕</button></td>
        {/if}
      </tr>
    {/each}
  </tbody>
</table>
