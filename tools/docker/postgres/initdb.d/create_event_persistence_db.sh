#!/bin/bash
# Create the event persistence database if it does not exist.
DB_NAME="${EDA_EVENT_PERSISTENCE_DB_NAME:-eda_event_persistence}"
DB_USER="${EDA_EVENT_PERSISTENCE_DB_USER:-eda}"

psql -U postgres -v db_name="${DB_NAME}" -v db_user="${DB_USER}" <<-'EOSQL'
    SELECT 'CREATE ROLE "' || :'db_user' || '" LOGIN'
    WHERE NOT EXISTS (
        SELECT FROM pg_roles WHERE rolname = :'db_user'
    )\gexec

    SELECT 'CREATE DATABASE "' || :'db_name' || '" OWNER "' || :'db_user' || '"'
    WHERE NOT EXISTS (
        SELECT FROM pg_database WHERE datname = :'db_name'
    )\gexec
EOSQL
