import { EmConstrucao } from "@/shared/ui/EmConstrucao";

/** Tela "Riscos de Dados Pessoais" — referência visual: prototipos/prototipoV1.html. Substituir pelo conteúdo real. */
export default function LgpdPage() {
  return (
    <EmConstrucao
      titulo="Riscos de Dados Pessoais"
      descricao="Detecção e priorização de possíveis dados pessoais para análise humana, com anonimização aprovada por quem tem a permissão de aprovação."
      userStories={["US11", "US12", "US13", "US26", "US27"]}
    />
  );
}
