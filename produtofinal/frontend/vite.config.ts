import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Sem @types/node no projeto: declara só o que este arquivo lê do ambiente.
declare const process: { env: Record<string, string | undefined> };

// Variáveis usadas só no modo desenvolvimento em container (docker-compose.dev.yml, ADR-0017).
const hmrClientPort = process.env.VITE_HMR_CLIENT_PORT;

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": "/src" } },
  server: {
    port: 5173,
    // xfwd: repassa o IP de quem acessa, como o nginx faz em produção (log de acesso, ADR-0016)
    proxy: { "/api": { target: process.env.VITE_PROXY_API ?? "http://localhost:8000", xfwd: true } },
    // Pasta do Windows montada no container não dispara eventos de arquivo: verifica por polling.
    watch: process.env.VITE_POLLING ? { usePolling: true, interval: 300 } : undefined,
    // O navegador acessa :8080 (porta publicada), não a porta interna do container.
    hmr: hmrClientPort ? { clientPort: Number(hmrClientPort) } : undefined,
  },
});
