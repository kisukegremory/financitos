<script>
  import { dateBR, money } from './format.js'

  /** @type {{ items: any[], categories: string[], onchange?: (item: any, category: string) => void, onremove?: (item: any) => void }} */
  let { items, categories, onchange, onremove } = $props()
</script>

<table>
  <thead>
    <tr>
      <th>Data</th>
      <th class="num">Gasto</th>
      <th>Caixinha</th>
      <th>Descrição</th>
      <th>Fonte</th>
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
        {#if onremove}
          <td><button class="ghost" title="Remover" onclick={() => onremove(item)}>✕</button></td>
        {/if}
      </tr>
    {/each}
  </tbody>
</table>
