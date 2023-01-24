import datetime
import json
import os
from io import StringIO

import django
import pytest
from django.contrib.postgres.fields import ArrayField
from django.db import connection, models, transaction
from psycopg2 import errors as pg_errors

from aap_eda.core.models import base

CREATE_TEST_TABLE = """
create table eek (
    id         serial primary key,
    label      text not null,
    data       jsonb,
    lista      int[],
    created_ts timestamptz
)
;
"""

DROP_TEST_TABLE = """
drop table if exists eek
;
"""


@pytest.fixture
def eek_temp_table():
    with connection.cursor() as cur:
        cur.execute(CREATE_TEST_TABLE)
    yield
    with connection.cursor() as cur:
        cur.execute(DROP_TEST_TABLE)


@pytest.fixture
def eek_model(eek_temp_table):
    if "eek" not in django.apps.apps.all_models["core"]:

        class Eek(models.Model):
            class Meta:
                app_label = "core"
                db_table = "eek"

            label = models.TextField(null=False)
            data = models.JSONField()
            lista = ArrayField(models.IntegerField())
            created_ts = models.DateTimeField()

    return django.apps.apps.all_models["core"]["eek"]


@pytest.fixture
def test_data():
    return {
        "cols": ["label", "data", "lista", "created_ts"],
        "data": [
            {
                "label": "label-1",
                "data": {"type": "rulebook", "data": {"ruleset": "ruleset-1"}},
                "lista": None,
                "created_ts": datetime.datetime.now(tz=datetime.timezone.utc),
            },
            {
                "label": "label-2",
                "data": None,
                "lista": [1, 2, 3, 4],
                "created_ts": datetime.datetime.now(tz=datetime.timezone.utc),
            },
        ],
    }


@pytest.fixture
def test_record():
    return {
        "id": 1,
        "name": "eek",
        "lista": None,
        "data": {"feels": "meh"},
        "created_ts": datetime.datetime.now(tz=datetime.timezone.utc),
        "links": [1, 2, 3, 4],
    }


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


def test_adapt_copy_types_dict(test_record):
    rec = test_record
    writer = base.DictCopyWriter(StringIO(), list(rec))
    mvals = {
        col: writer._adapt_copy_type(rec[col]) for col in writer.fieldnames
    }
    assert type(mvals) == dict
    assert len(mvals) == len(rec)
    assert type(mvals["id"]) == base.Copyfy
    assert type(mvals["name"]) == base.Copyfy
    assert type(mvals["lista"]) == base.Copyfy
    assert type(mvals["data"]) == base.CopyfyDict
    assert type(mvals["created_ts"]) == base.Copyfy
    assert type(mvals["links"]) == base.CopyfyListTuple


@pytest.mark.django_db
def test_model_writer_pk_switch(eek_model):
    writer = base.ModelCopyWriter(StringIO(), eek_model)
    assert eek_model._meta.pk.name not in writer.fieldnames
    writer = base.ModelCopyWriter(StringIO(), eek_model, pk_in_data=True)
    assert eek_model._meta.pk.name in writer.fieldnames


@pytest.mark.django_db
def test_adapt_copy_types_model(eek_model):
    eek = eek_model(
        label="test_model_adapt",
        data={"quatloos": 300},
        lista=[1, 2, 3],
    )
    writer = base.ModelCopyWriter(StringIO(), eek_model, pk_in_data=True)
    rec = writer._model_to_dict(eek)
    assert type(rec["id"]) == base.Copyfy
    assert type(rec["label"]) == base.Copyfy
    assert type(rec["data"]) == base.CopyfyDict
    assert type(rec["lista"]) == base.CopyfyListTuple
    assert type(rec["created_ts"]) == base.Copyfy


def test_adapted_values(test_record):
    cols = list(test_record)
    rec = test_record
    writer = base.DictCopyWriter(StringIO(), list(rec))
    mvals = dict(zip(cols, writer._dict_to_list(rec)))
    assert len(mvals) == len(rec)
    assert mvals["id"] == str(rec["id"])
    assert mvals["name"] == rec["name"]
    assert mvals["lista"] == base.DEFAULT_NULL
    assert mvals["data"] == json.dumps(rec["data"])
    assert mvals["created_ts"] == str(rec["created_ts"])
    assert mvals["links"] == "{1,2,3,4}"


def verify_copied_data(expected, db_data):
    assert len(db_data) == len(expected)
    for i, dat in enumerate(db_data):
        exp = expected[i]
        for k in dat:
            if k == "id":
                assert isinstance(dat[k], int)
            else:
                assert exp[k] == dat[k]


def write_to_copy_file(cols, data):
    copy_file = StringIO()
    writer = base.DictCopyWriter(copy_file, cols)
    writer.writerows(data)
    copy_file.seek(0)

    return copy_file


@pytest.mark.django_db
def test_copy_to_table(eek_model, test_data):
    cols = test_data["cols"]
    expected = test_data["data"]

    copy_file = write_to_copy_file(cols, expected)
    base.copy_to_table(connection, "eek", cols, copy_file)

    db_result = list(eek_model.objects.values())
    verify_copied_data(expected, db_result)


@pytest.mark.django_db
def test_copy_to_table_with_sep(eek_model, test_data):
    new_sep = "|"
    cols = test_data["cols"]
    expected = test_data["data"]

    copy_file = StringIO()
    # Checking calls to writerow
    writer = base.DictCopyWriter(copy_file, cols, delimiter=new_sep)
    for exp in expected:
        writer.writerow(exp)

    # Verify file data
    copy_file.seek(0)
    file_recs = [
        line for line in copy_file.read().split(os.linesep) if len(line) > 0
    ]
    assert len(file_recs) == len(expected)
    assert file_recs[0].count(new_sep) == len(expected[0]) - 1
    assert file_recs[1].count(new_sep) == len(expected[1]) - 1

    copy_file.seek(0)
    base.copy_to_table(connection, "eek", cols, copy_file, sep=new_sep)

    db_data = list(eek_model.objects.values())
    verify_copied_data(expected, db_data)


@pytest.mark.django_db
def test_copy_to_table_file_error(eek_temp_table, test_data):
    cols = test_data["cols"]
    data = test_data["data"]

    copy_file = write_to_copy_file(cols, data)

    cols = cols[:3]

    with pytest.raises(pg_errors.BadCopyFileFormat):
        with transaction.atomic():
            base.copy_to_table(
                connection,
                "eek",
                cols,
                copy_file,
            )


@pytest.mark.django_db
def test_copy_to_table_integrity_error(eek_temp_table, test_data):
    cols = test_data["cols"]
    data = test_data["data"]

    data[0]["label"] = None

    copy_file = write_to_copy_file(cols, data)

    with pytest.raises(pg_errors.NotNullViolation):
        with transaction.atomic():
            base.copy_to_table(
                connection,
                "eek",
                cols,
                copy_file,
            )
