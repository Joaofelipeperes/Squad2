# Certificados (HTTPS próprio)

Deixe esta pasta **vazia** quando houver um proxy reverso com HTTPS na frente (UFG, ou o proxy da
CGE-GO). A aplicação então serve HTTP na porta `GDA_PORTA_HTTP`.

Para a própria aplicação fazer o HTTPS, coloque aqui:

- `fullchain.pem` — certificado do domínio com a cadeia intermediária;
- `privkey.pem` — chave privada (permissão `600`).

Depois rode `docker compose up -d --force-recreate web`. A porta HTTP passa a redirecionar para a HTTPS
(`GDA_PORTA_HTTPS`). Os arquivos `.pem` nunca são versionados.
