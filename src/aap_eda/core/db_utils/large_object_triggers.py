from typing import List, Optional

from django.db import models
from django.utils.connection import ConnectionProxy

__all__ = (
    "create_large_object_trigger_func_sql",
    "drop_create_large_object_func_sql",
    "delete_large_object_trigger_func_sql",
    "drop_delete_large_object_func_sql",
    "apply_large_object_triggers",
    "unapply_large_object_triggers",
)


def create_large_object_trigger_func_sql() -> str:
    return """
create or replace function trfn_create_lobject()
returns trigger
as $$
begin
    if new.large_data_id is null
    then
        select lo_create(0)
          into new.large_data_id;
    end if;

    return new;
end;
$$ language plpgsql
;
    """


def drop_create_large_object_func_sql() -> str:
    return """
drop function if exists trfn_create_lobject() cascade
;
    """


def delete_large_object_trigger_func_sql() -> str:
    return """
create or replace function trfn_cascade_delete_lobject()
returns trigger
as $$
begin
    perform lo_unlink(d.large_data_id)
      from deleted_records d;

    return null;
end;
$$ language plpgsql
;
    """


def drop_delete_large_object_func_sql() -> str:
    return """
drop function if exists trfn_cascade_delete_lobject() cascade
;
    """


def get_applied_large_object_trigger_table_info(
    conn: ConnectionProxy,
) -> List[dict]:
    sql = """
select c.relname as "table_name",
       coalesce(t.trigger_funcs, '{}'::text[]) as "trigger_funcs"
  from pg_attribute a
  join pg_class c
    on c.oid = a.attrelid
   and c.relkind = 'r'
  left
  join
  lateral (
            select array_agg(pt.tgfoid::regproc::text) as "trigger_funcs"
              from pg_trigger pt
             where pt.tgrelid = c.oid
               and not pt.tgisinternal
               and pt.tgfoid::regproc::text in (
                       'trfn_create_lobject',
                       'trfn_cascade_delete_lobject'
                   )
          ) t
    on true
 where a.attname = 'large_data_id'
;
    """  # noqa: P103
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, rec)) for rec in cur.fetchall()]


def apply_large_object_triggers(
    conn: ConnectionProxy, *, models: Optional[List[models.Model]] = None
):
    create_trigger_tmpl = """
create trigger tr_{db_table}_lob
before insert
    on {db_table}
   for each row
       execute function trfn_create_lobject()
;
    """
    delete_trigger_tmpl = """
create trigger tr_{db_table}_cascade_delete_lob
 after delete
    on {db_table}
       referencing old table as deleted_records
   for each statement
       execute function trfn_cascade_delete_lobject();
    """

    table_info = get_applied_large_object_trigger_table_info(conn)
    if models:
        models = [m._meta.db_table for m in models]
    for tab_rec in table_info:
        tab_name = tab_rec["table_name"]
        trig_funcs = tab_rec["trigger_funcs"]
        if not models or tab_name in models:
            create_func = "trfn_create_lobject"
            delete_func = "trfn_cascade_delete_lobject"
            if create_func not in trig_funcs:
                with conn.cursor() as cur:
                    cur.execute(create_trigger_tmpl.format(db_table=tab_name))
            if delete_func not in trig_funcs:
                with conn.cursor() as cur:
                    cur.execute(delete_trigger_tmpl.format(db_table=tab_name))


def unapply_large_object_triggers(
    conn: ConnectionProxy, *, models: Optional[List[models.Model]] = None
):
    delete_trigger_tmpl = [
        """
drop trigger if exists tr_{db_table}_lob on {db_table} ;
        """,
        """
drop trigger if exists tr_{db_table}_cascade_delete_lob on {db_table} ;
        """,
    ]

    table_info = get_applied_large_object_trigger_table_info(conn)
    if models:
        models = [m._meta.db_table for m in models]
    for tab_rec in table_info:
        tab_name = tab_rec["table_name"]
        if not models or tab_name in models:
            with conn.cursor() as cur:
                for drop_stmt in delete_trigger_tmpl:
                    cur.execute(drop_stmt.format(db_table=tab_name))
