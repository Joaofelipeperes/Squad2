#!/bin/sh
# Monta a configuração do nginx ao iniciar o container (ADR-0032). Roda pelo /docker-entrypoint.d
# da imagem oficial, antes do nginx subir.
#   GDA_PROXY_CONFIAVEL  IPs/CIDRs do proxy reverso, separados por espaço ou vírgula. Só deles o
#                        X-Forwarded-For (IP real do usuário) é aceito (ADR-0016). Padrão: nenhum.
#   GDA_PORTA_HTTPS      porta HTTPS pública, para o redirecionamento (padrão 443).
# Certificado em /etc/nginx/certs/{fullchain,privkey}.pem → modo HTTPS; senão, modo HTTP.
set -eu
D=/etc/nginx/gda

: > "$D/real-ip.conf"
for ip in $(echo "${GDA_PROXY_CONFIAVEL:-}" | tr ',' ' '); do
    echo "set_real_ip_from $ip;" >> "$D/real-ip.conf"
done
if [ -s "$D/real-ip.conf" ]; then
    printf 'real_ip_header X-Forwarded-For;\nreal_ip_recursive on;\n' >> "$D/real-ip.conf"
fi

porta="${GDA_PORTA_HTTPS:-443}"
if [ "$porta" = "443" ]; then destino='https://$host$request_uri'; else destino="https://\$host:$porta\$request_uri"; fi
echo "location / { return 301 $destino; }" > "$D/redirect.conf"

if [ -f /etc/nginx/certs/fullchain.pem ] && [ -f /etc/nginx/certs/privkey.pem ]; then
    cp "$D/https.conf" /etc/nginx/conf.d/default.conf
    modo=HTTPS
else
    cp "$D/http.conf" /etc/nginx/conf.d/default.conf
    modo=HTTP
fi
echo "gda: modo $modo; proxy confiável: ${GDA_PROXY_CONFIAVEL:-nenhum}"
