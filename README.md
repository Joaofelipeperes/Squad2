# CkanSquad2 — CKAN 2.9.5 Infrastructure

Este repositório contém a infraestrutura containerizada utilizando **Docker Compose** para a plataforma de dados abertos **CKAN 2.9.5**, incluindo o PostgreSQL (com PostGIS), Solr e Redis.

---

## Pré-requisitos

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução.
* [Git](https://git-scm.com/) instalado.

---

## Passo a Passo para Subir o Ambiente

Siga as instruções abaixo para clonar e rodar o ambiente localmente:

### 1. Clonar o repositório

git clone [https://github.com/SEU_USUARIO/CkanSquad2.git](https://github.com/SEU_USUARIO/CkanSquad2.git)
cd CkanSquad2

### 2. Subir os Containers Docker
Execute o comando para construir e iniciar todos os serviços em segundo plano:

docker compose up -d

### 3. Inicializar o Banco de Dados
Após a subida dos containers, inicialize as tabelas do PostgreSQL e do Solr:

docker compose exec ckan ckan db init

### 4. Criar o Usuário Administrador (Sysadmin)
Crie um usuário com permissões completas de administrador para gerenciar o portal:

Após seguir os passos acima, a interface do CKAN estará disponível em:

URL: http://localhost:5000

Usuário Sysadmin: admin

Para verificar o status dos componentes e da versão da API:

Status da API: http://localhost:5000/api/3/action/status_show

