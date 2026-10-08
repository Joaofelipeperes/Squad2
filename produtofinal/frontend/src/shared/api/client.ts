/** Cliente HTTP único. Todas as chamadas à API passam por aqui (token + tratamento de erro). */
const BASE = "/api/v1";
const TOKEN_KEY = "gda.token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

/**
 * Executa a requisição com token e tratamento de erro comuns.
 * `contentType` ausente = o navegador define o cabeçalho (necessário no multipart/form-data,
 * que leva o boundary gerado pelo próprio navegador).
 */
async function executar<T>(method: string, path: string, body?: BodyInit, contentType?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (contentType) headers["Content-Type"] = contentType;
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${BASE}${path}`, { method, headers, body });
  if (resp.status === 401) {
    tokenStore.clear();
    window.dispatchEvent(new Event("gda:sessao-expirada"));
  }
  if (!resp.ok) {
    let msg = `Erro ${resp.status}`;
    try {
      const data = await resp.json();
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail)) msg = data.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* resposta sem JSON */
    }
    throw new ApiError(resp.status, msg);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  return executar<T>(method, path, body === undefined ? undefined : JSON.stringify(body), "application/json");
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b),
  put: <T>(p: string, b?: unknown) => request<T>("PUT", p, b),
  del: <T>(p: string) => request<T>("DELETE", p),
  /** POST multipart/form-data (envio de arquivo). Não define Content-Type: o navegador põe o boundary. */
  upload: <T>(p: string, form: FormData) => executar<T>("POST", p, form),
};
