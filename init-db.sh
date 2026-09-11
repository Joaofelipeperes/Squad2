#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER datastore_ro WITH PASSWORD 'ckan';
    CREATE DATABASE datastore OWNER ckan;
    GRANT ALL PRIVILEGES ON DATABASE datastore TO ckan;
EOSQL