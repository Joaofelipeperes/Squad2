/**
 * Endereço vindo do CKAN (link de recurso, escrito pelo órgão) só vira link se for http ou https.
 * Outros esquemas (`javascript:`, `data:`) executariam código no navegador de quem clica.
 */
export function urlSegura(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url, window.location.origin);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
