/**
 * REGISTRO DE MÓDULOS — único lugar a editar para incluir/remover uma tela.
 * A ordem da lista é a ordem do menu dentro de cada seção. Cada tela declara a permissão que
 * exige; o filtro por usuário é feito em app/App.tsx.
 */
import { atualizacoesModule } from "@/modules/atualizacoes";
import { assistenteWidget } from "@/modules/assistente";
import { dashboardModule } from "@/modules/dashboard";
import { datasetsModule } from "@/modules/datasets";
import { envioModule } from "@/modules/envio";
import { iaModule } from "@/modules/ia";
import { lgpdModule } from "@/modules/lgpd";
import { organizacoesModule } from "@/modules/organizacoes";
import { parametrosModule } from "@/modules/parametros";
import { pdaModule } from "@/modules/pda";
import { rastreabilidadeModule } from "@/modules/rastreabilidade";
import { relatoriosModule } from "@/modules/relatorios";
import { usuariosModule } from "@/modules/usuarios";
import type { AppModule, AppWidget } from "@/modules/types";

export const MODULOS: AppModule[] = [
  dashboardModule,
  pdaModule,
  atualizacoesModule,
  lgpdModule,
  organizacoesModule,
  datasetsModule,
  rastreabilidadeModule,
  relatoriosModule,
  envioModule,
  iaModule,
  parametrosModule,
  usuariosModule,
];

export const WIDGETS: AppWidget[] = [assistenteWidget];
