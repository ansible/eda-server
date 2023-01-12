import datetime
import json
from io import StringIO

import pytest
from django.contrib.postgres.fields import ArrayField
from django.db import models
from psycopg2 import DatabaseError, DataError, connect as pg_connect

from aap_eda.core.models import Project, base


def get_wrapped_connection():
    """Get a separate connection to tests exceptions."""
    from django.db import connection

    class PGCurWrapper:
        def __init__(self, cur):
            self.cursor = cur

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs):
            self.cursor.close()

        def execute(self, sql, params=None):
            self.cursor.execute(sql, params)

    class PGConnWrapper:
        def __init__(self, dsn):
            self.connection = pg_connect(dsn)

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs):
            self.connection.close()

        def cursor(self):
            return PGCurWrapper(self.connection.cursor())

        def commit(self):
            self.connection.commit()

        def rollback(self):
            self.connection.rollback()

    db_url = (
        "postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}"
        "?sslmode=prefer&application_name=eda_test_exc"
    ).format(**connection.settings_dict)

    return PGConnWrapper(db_url)


def get_create_test_table_sql():
    return """
create table eek (
    id         serial primary key,
    label      text not null,
    data       jsonb,
    lista      int[],
    created_ts timestamptz
)
;
    """


def get_drop_test_table_sql():
    return "drop table if exists eek;"


def test_oid_field_int():
    assert base.OIDField == models.IntegerField


def test_copyfy_class():
    assert str(base.Copyfy(None)) == base.DEFAULT_NULL
    assert str(base.Copyfy("eek")) == "eek"
    assert str(base.Copyfy(1)) == "1"


def test_copyfydict():
    d = {"star": "trek", "quatloos": 200}
    assert str(base.CopyfyDict(d)) == json.dumps(d)
    assert str(base.CopyfyDict({})) == "{}"  # noqa: P103
    assert str(base.CopyfyDict(None)) == base.DEFAULT_NULL


def test_copyfylisttuple():
    assert str(base.CopyfyListTuple(list("asdf"))) == "{a,s,d,f}"
    assert str(base.CopyfyListTuple([])) == "{}"  # noqa: P103
    assert str(base.CopyfyListTuple(None)) == base.DEFAULT_NULL
    assert str(base.CopyfyListTuple([[1, 2], [3, 4]])) == "{{1,2},{3,4}}"


def test_adapt_copy_types():
    vals = [
        1,
        "eek",
        None,
        {"feels": "meh"},
        datetime.datetime.now(tz=datetime.timezone.utc),
        [1, 2, 3, 4],
    ]
    mvals = base.adapt_copy_types(vals)
    assert type(mvals) == list
    assert len(mvals) == len(vals)
    assert type(mvals[0]) == base.Copyfy
    assert type(mvals[1]) == base.Copyfy
    assert type(mvals[2]) == base.Copyfy
    assert type(mvals[2]) == base.Copyfy
    assert type(mvals[3]) == base.CopyfyDict
    assert type(mvals[4]) == base.Copyfy
    assert type(mvals[5]) == base.CopyfyListTuple

    mvals = base.adapt_copy_types(tuple(vals))
    assert type(mvals) == tuple


def test_copyfy_values(db):
    vals = [
        1,
        "eek",
        None,
        {"feels": "meh"},
        datetime.datetime.now(tz=datetime.timezone.utc),
        [1, 2, 3, 4],
    ]
    mvals = base.copyfy_values(vals)
    assert isinstance(mvals, str)
    assert base.DEFAULT_SEP in mvals
    mvals_list = mvals.split(base.DEFAULT_SEP)
    assert len(mvals_list) == len(vals)
    assert mvals_list[0] == str(vals[0])
    assert mvals_list[1] == str(vals[1])
    assert mvals_list[2] == base.DEFAULT_NULL
    assert mvals_list[3] == json.dumps(vals[3])
    assert mvals_list[4] == str(vals[4])
    assert mvals_list[5] == str(base.CopyfyListTuple(vals[5]))


@pytest.mark.django_db
def test_copy_to_table():
    from django.db import connection as db

    with db.cursor() as cur:
        cur.execute(get_create_test_table_sql())

    class Eek(models.Model):
        class Meta:
            app_label = "core"
            db_table = "eek"

        label = models.TextField(null=False)
        data = models.JSONField()
        lista = ArrayField(models.IntegerField())
        created_ts = models.DateTimeField()

    try:
        cols = ["label", "data", "lista", "created_ts"]
        vals = [
            [
                "label-1",
                {"type": "rulebook", "data": {"ruleset": "ruleset-1"}},
                None,
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
            [
                "label-2",
                None,
                [1, 2, 3, 4],
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
        ]

        copy_file = StringIO()
        for val in vals:
            print(base.copyfy_values(val), file=copy_file)  # noqa:T201
        copy_file.seek(0)

        base.copy_to_table(db, "eek", cols, copy_file)

        res = list(Eek.objects.values_list())
        assert len(res) == 2
        for i, rec in enumerate(res):
            val = vals[i]
            for j in range(len(rec)):
                if j == 0:
                    assert isinstance(rec[j], int)
                else:
                    assert val[j - 1] == rec[j]

    finally:
        with db.cursor() as cur:
            cur.execute(get_drop_test_table_sql())


@pytest.mark.django_db
def test_copy_to_table_with_sep():
    from django.db import connection as db

    with db.cursor() as cur:
        cur.execute(get_create_test_table_sql())

    class EekWithSep(models.Model):
        class Meta:
            app_label = "core"
            db_table = "eek"

        label = models.TextField(null=False)
        data = models.JSONField()
        lista = ArrayField(models.IntegerField())
        created_ts = models.DateTimeField()

    try:
        cols = ["label", "data", "lista", "created_ts"]
        vals = [
            [
                "label-1",
                {"type": "rulebook", "data": {"ruleset": "ruleset-1"}},
                None,
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
            [
                "label-2",
                None,
                [1, 2, 3, 4],
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
        ]

        copy_file = StringIO()
        for val in vals:
            copy_rec = base.copyfy_values(val, sep="|")
            print(copy_rec, file=copy_file)  # noqa:T201
        copy_file.seek(0)

        base.copy_to_table(db, "eek", cols, copy_file, sep="|")

        res = list(EekWithSep.objects.values_list())
        assert len(res) == 2
        for i, rec in enumerate(res):
            val = vals[i]
            for j in range(len(rec)):
                if j == 0:
                    assert isinstance(rec[j], int)
                else:
                    assert val[j - 1] == rec[j]

    finally:
        with db.cursor() as cur:
            cur.execute(get_drop_test_table_sql())


@pytest.mark.django_db
def test_copy_to_table_file_error():
    with get_wrapped_connection() as db:
        with db.cursor() as cur:
            cur.execute(get_create_test_table_sql())

        cols = ["label", "data", "created_ts"]
        vals = [
            [
                "label-1",
                {"type": "rulebook", "data": {"ruleset": "ruleset-1"}},
                None,
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
            [
                "label-2",
                None,
                [1, 2, 3, 4],
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
        ]

        copy_file = StringIO()
        for val in vals:
            print(base.copyfy_values(val), file=copy_file)  # noqa:T201
        copy_file.seek(0)

        with pytest.raises(DataError):
            base.copy_to_table(
                db,
                "eek",
                cols,
                copy_file,
            )

        db.rollback()

        with db.cursor() as cur:
            cur.execute(get_drop_test_table_sql())


@pytest.mark.django_db
def test_copy_to_table_integrity_error():
    with get_wrapped_connection() as db:
        with db.cursor() as cur:
            cur.execute(get_create_test_table_sql())

        cols = ["label", "data", "lista", "created_ts"]
        vals = [
            [
                None,
                {"type": "rulebook", "data": {"ruleset": "ruleset-1"}},
                None,
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
            [
                "label-2",
                None,
                [1, 2, 3, 4],
                datetime.datetime.now(tz=datetime.timezone.utc),
            ],
        ]

        copy_file = StringIO()
        for val in vals:
            print(base.copyfy_values(val), file=copy_file)  # noqa:T201
        copy_file.seek(0)

        with pytest.raises(DatabaseError):
            base.copy_to_table(
                db,
                "eek",
                cols,
                copy_file,
            )

        db.rollback()

        with db.cursor() as cur:
            cur.execute(get_drop_test_table_sql())


def test_copyfy_model():
    kwargs = {
        "name": "proj-1",
        "description": "test project",
    }
    p = Project(**kwargs)
    p_mog = p.copyfy()
    p_mog_values = p_mog.split(base.DEFAULT_SEP)
    assert len(p_mog_values) == len(p._meta.concrete_fields)


def test_copyfy_model_with_sep():
    kwargs = {
        "name": "proj-1",
        "description": "test project",
    }
    p = Project(**kwargs)
    p_mog = p.copyfy(sep="|")
    p_mog_values = p_mog.split("|")
    assert len(p_mog_values) == len(p._meta.concrete_fields)


def test_copyfy_model_with_fields():
    kwargs = {
        "name": "proj-1",
        "description": "test project",
    }
    p = Project(**kwargs)
    mog_fields = ["name", "description"]
    p_mog = p.copyfy(fields=mog_fields)
    p_mog_values = p_mog.split(base.DEFAULT_SEP)
    assert len(p_mog_values) == len(mog_fields)
