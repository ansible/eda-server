#  Copyright 2022 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import csv
import json
import os
from typing import Any, Dict, Iterable, TextIO, Union

from django.contrib.postgres.fields import ArrayField
from django.db import ConnectionProxy, models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import JSONField

DEFAULT_SEP = "\t"
DEFAULT_NULL = "__N__"


class PGCopyDialect(csv.Dialect):
    quotechar = "'"
    escapechar = "\\"
    lineterminator = os.linesep
    delimiter = DEFAULT_SEP
    null = DEFAULT_NULL
    quoting = csv.QUOTE_NONE


csv.register_dialect("pg_copy", PGCopyDialect)


class Copyfy:
    ALLOWED_TYPES = ()

    def __init__(self, wrapped: Any):
        if (
            wrapped is not None
            and len(self.ALLOWED_TYPES) > 0
            and not isinstance(wrapped, self.ALLOWED_TYPES)
        ):
            allowed_types = ", ".join(self.ALLOWED_TYPES)
            raise TypeError(
                f"wrapped must be one of these instances: {allowed_types}"
            )

        self.wrapped = wrapped

    def __str__(self):
        if self.wrapped is None:
            return DEFAULT_NULL

        return self.stringify(self.wrapped)

    def stringify(self, wrapped: Any) -> str:
        return str(wrapped)


class CopyfyDict(Copyfy):
    ALLOWED_TYPES = (dict,)

    def stringify(self, wrapped: Dict) -> str:
        out = json.dumps(wrapped)
        if len(out) == 0:
            out = "{}"  # noqa: P103

        return out


class CopyfyListTuple(Copyfy):
    ALLOWED_TYPES = (list, tuple)

    def stringify(self, wrapped: Any) -> str:
        out = []

        for val in wrapped:
            if isinstance(val, (list, tuple)):
                str_val = self.stringify(val)
            elif isinstance(val, dict):
                str_val = str(CopyfyDict(val))
            elif val is None:
                str_val = DEFAULT_NULL
            else:
                str_val = super().stringify(val)

            out.append(str_val)

        return f"{{{','.join(out)}}}"


ADAPT_COPY_MAP = {
    dict: CopyfyDict,
    list: CopyfyListTuple,
    tuple: CopyfyListTuple,
    ArrayField: CopyfyListTuple,
    JSONField: CopyfyDict,
}


class DictCopyWriter(csv.DictWriter):
    def __init__(
        self,
        copyfile: TextIO,
        fieldnames: Iterable[str],
        restval=DEFAULT_NULL,
        *args,
        **kwargs,
    ):
        if "dialect" in kwargs:
            kwargs.pop("dialect")

        if "extrasaction" in kwargs:
            kwargs.pop("extrasaction")

        super().__init__(
            copyfile,
            fieldnames,
            restval=restval,
            extrasaction="raise",
            dialect="pg_copy",
            *args,
            **kwargs,
        )
        self.restval = Copyfy(self.restval)

    def _adapt_copy_type(self, obj: Any) -> Copyfy:
        if isinstance(obj, Copyfy):
            return obj
        return ADAPT_COPY_MAP.get(type(obj), Copyfy)(obj)

    def _dict_to_list(self, rowdict: Dict):
        if self.extrasaction == "raise":
            wrong_fields = rowdict.keys() - self.fieldnames
            if wrong_fields:
                raise ValueError(
                    "dict contains fields not in fieldnames: "
                    + ", ".join([repr(x) for x in wrong_fields])
                )
        return (
            str(self._adapt_copy_type(rowdict.get(key, self.restval)))
            for key in self.fieldnames
        )

    def writeheader(self):
        raise NotImplementedError("Writing header not supported.")


class ModelCopyWriter(DictCopyWriter):
    def __init__(
        self,
        copyfile: TextIO,
        model: models.Model,
    ):
        self.model = model
        # Sets fieldnames, fieldtypes
        self._resolve_fields()
        super().__init__(copyfile, self.fieldnames)

    def _resolve_fields(self):
        self.fieldnames = []
        self.fieldtypes = {}

        for field in self.model._meta.concrete_fields:
            self.fieldnames.append(field.name)
            self.fieldtypes[field.name] = type(field)

    def _model_to_dict(self, row: models.Model) -> Dict:
        ft = self.fieldtypes
        return {
            col: ADAPT_COPY_MAP.get(ft[col], Copyfy)(getattr(row, col, None))
            for col in self.fieldnames
        }

    def _dict_to_list(self, model: models.Model) -> Dict:
        return super()._dict_to_list(self._model_to_dict(model))


OIDField = models.IntegerField


def copy_to_table(
    conn: Union[BaseDatabaseWrapper, ConnectionProxy],
    db_table: str,
    columns: Iterable[str],
    data: TextIO,
    *,
    sep: str = DEFAULT_SEP,
) -> None:
    """Read data from a file-like object and write to DB table using COPY."""
    with conn.cursor() as cur:
        cur.cursor.copy_from(
            data,
            db_table,
            sep=sep,
            null=DEFAULT_NULL,
            columns=columns,
        )


__all__ = (
    "Copyfy",
    "CopyfyDict",
    "CopyfyListTuple",
    "DictCopyWriter",
    "ModelCopyWriter",
    "OIDField",
    "copy_to_table",
)
