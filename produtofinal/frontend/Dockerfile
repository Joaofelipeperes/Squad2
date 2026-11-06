FROM node:20-alpine AS build
WORKDIR /web
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# Template: a imagem do nginx aplica envsubst (só variáveis definidas) e gera conf.d/default.conf
COPY nginx.conf /etc/nginx/templates/default.conf.template
# Proxy reverso confiável para o IP real (ADR-0016); o docker-compose sobrescreve pelo .env
ENV GDA_PROXY_CONFIAVEL=127.0.0.1
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
