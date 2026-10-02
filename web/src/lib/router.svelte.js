// Roteador mínimo por path (history API). O backend devolve index.html para
// qualquer rota fora de /api, então /financitos e /tarot funcionam no F5.
export const route = $state({ path: location.pathname })

addEventListener('popstate', () => (route.path = location.pathname))

export function navigate(path) {
  if (path === route.path) return
  history.pushState({}, '', path)
  route.path = path
}

// <a href="/tarot" onclick={link}> navega sem recarregar a página
export function link(event) {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return
  event.preventDefault()
  navigate(event.currentTarget.getAttribute('href'))
}
