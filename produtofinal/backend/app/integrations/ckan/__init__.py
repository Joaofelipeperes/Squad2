"""Integração com o CKAN 2.9.5 do Portal de Dados Abertos de Goiás.

- client.py  → LEITURA pela API pública (sem autenticação). Usado pela coleta diária.
- writer.py  → ESCRITA, restrita à publicação de recurso anonimizado (US26). Desligada por padrão.
"""
