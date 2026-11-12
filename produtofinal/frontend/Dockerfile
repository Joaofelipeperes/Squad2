FROM node:20-alpine AS build
WORKDIR /web
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# Configuração montada ao iniciar por 30-gda-config.sh (ADR-0032): modo HTTP atrás de proxy ou
# HTTPS próprio (certificado em /etc/nginx/certs), proxy confiável pelo GDA_PROXY_CONFIAVEL
COPY nginx/*.conf /etc/nginx/gda/
COPY nginx/30-gda-config.sh /docker-entrypoint.d/30-gda-config.sh
RUN chmod +x /docker-entrypoint.d/30-gda-config.sh && rm -f /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80 443
