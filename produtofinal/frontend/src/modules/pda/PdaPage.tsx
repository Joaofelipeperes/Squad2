import { EmConstrucao } from "@/shared/ui/EmConstrucao";

/** Tela "Monitoramento do PDA" — referência visual: prototipos/prototipoV1.html. Substituir pelo conteúdo real. */
export default function PdaPage() {
  return (
    <EmConstrucao
      titulo="Monitoramento do PDA"
      descricao="Acompanhamento das bases previstas no Plano de Dados Abertos em relação à publicação efetiva no CKAN."
      userStories={["US6", "US7", "US8"]}
    />
  );
}
