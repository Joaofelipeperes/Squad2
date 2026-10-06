import { EmConstrucao } from "@/shared/ui/EmConstrucao";

/** Tela "Visão Geral" — referência visual: prototipos/prototipoV1.html. Substituir pelo conteúdo real. */
export default function DashboardPage() {
  return (
    <EmConstrucao
      titulo="Visão Geral"
      descricao="Monitoramento do Portal de Dados Abertos de Goiás — camada de governança externa ao CKAN. Consolida o cumprimento do PDA, a atualização real dos recursos e sinalizações de possíveis dados pessoais."
      userStories={["US19", "US25"]}
    />
  );
}
