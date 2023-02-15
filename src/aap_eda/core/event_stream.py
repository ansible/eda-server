#! /usr/bin/env python
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

DEFAULT_CHUNK_SIZE = 4000


# This class is the consumer. It will chunk events together before calling a
# supplied writer to write the data.
# This was done to try to accomodate usage in multiple projects.
# This could be subclassed to be a consumer for a specific project.
#
# Required:
#  event_writer   : Callable - Write chunks to DB.
#                              Parameters:
#                                chunk_meta: EventConsumer.ChunkData,
#                                chunk_data: Any,
#  event_reader   : Iterable - Iterable from which events will be received.
#  event_parser   : Callable - Receive raw event, parse into a structure that
#                              can be used by the writer and forwarder.
#                              The text of the event should be collected and
#                              Parsed as full lines if possible.
#                              Parameters:
#                                event: Any,
#  event_forwarder: Callable - Function to forward the event to other
#                              processing code (such as websocket
#                              transmission). This data will be the output
#                              from the parser function.
#                              Parameters:
#                                event_data: Any (output from parser),
#  chunk_size     : int      - Number of bytes that should make up a chunk.
#                              Once enough lines are read (or StopIteration)
#                              The chunk will be written to the database.
class EventConsumer:
    # Class specific to the consumer.
    # It will track this data and pass it to the writer.
    class ChunkMeta:
        def __init__(
            self,
            chunk_number: int,
            start_line: int,
            end_line: int,
            created: Optional[datetime] = None,
        ):
            self.chunk_created = (
                datetime.now(tz=timezone.utc) if not created else created
            )
            self.chunk_number = chunk_number
            self.stream_start_line = start_line
            self.stream_end_line = end_line

    def __init__(
        self,
        /,
        event_writer: Callable,
        event_reader: Iterable,
        event_parser: Callable,
        event_forwarder: Optional[Callable] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.writer = event_writer
        self.reader = event_reader
        self.parser = event_parser
        self.forwarder = event_forwarder
        self.chunk_size = chunk_size
        self.__consumed_events = 0
        self.__chunks_written = 0

    @property
    def consumed_events(self):
        return self.__consumed_events

    @property
    def chunks_written(self):
        return self.__chunks_written

    def consume(self):
        chunk_data = []
        chunk_len = 0
        start_line = 1
        end_line = 0

        for event in self.reader:
            self.__consumed_events += 1
            event_data = self.parser(event)
            chunk_len += len(event_data.event_text)
            end_line += event_data.text_line_count
            chunk_data.append(event_data)

            if chunk_len > self.chunk_size:
                self.__chunks_written += 1
                self.writer(
                    self.ChunkMeta(
                        self.__chunks_written, start_line, end_line
                    ),
                    chunk_data,
                )
                chunk_data = []
                chunk_len = 0
                start_line = end_line + 1

            if self.forwarder:
                self.forwarder(event_data)

        if chunk_data:
            self.__chunks_written += 1
            self.writer(
                self.ChunkMeta(self.__chunks_written, start_line, end_line),
                chunk_data,
            )


# =====================================================================
# =====================================================================
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
from uuid import uuid4  # noqa: E402

from django.db import connection, models  # noqa: E402
from faker import Faker  # noqa: E402

Faker.seed(time.time())
FAKE = Faker()
NLREGEX = re.compile(r"\r\n?|\n")


connection.connect()


# Generic structure to pass data around to the function handlers
class EventStruct:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def as_dict(self) -> Dict:
        return self.__dict__.copy()


# Create the table so we dont have to try to run migrations.
# This is just a PoC
def create_table():
    sql = [
        """
create extension if not exists "uuid-ossp" schema public;
        """,
        """
create table if not exists public.core_job_events_stream (
    id  uuid primary key default uuid_generate_v4(),
    job_id uuid not null,
    job_created timestamptz not null,
    event_chunk_created timestamptz not null,
    event_chunk_num bigint not null,
    event_chunk_start_line bigint,
    event_chunk_end_line bigint,
    event_chunk_text text not null default ''
);
        """,
        """
create index if not exists ix_job_event_job_id
    on core_job_events_stream (job_id);
        """,
        """
create table if not exists public.core_job_events_stream_data (
    id  uuid primary key default uuid_generate_v4(),
    job_id uuid not null,
    stream_chunk_id uuid not null
                    references public.core_job_events_stream (id)
                            on delete cascade,
    stream_chunk_line bigint,
    event_data jsonb
);
        """,
        """
create index if not exists ix_job_data_job_id
    on core_job_events_stream_data (job_id);
        """,
    ]
    with connection.cursor() as cur:
        for stmt in sql:
            cur.execute(stmt)


# Utility function
def count_lines(buff: str) -> int:
    bufflen = len(buff)
    nlfound = list(NLREGEX.finditer(buff))
    if nlfound:
        num_lines = len(nlfound) + int(nlfound[-1].end() < bufflen)
    else:
        num_lines = int(bufflen > 0)

    return num_lines


# Take the raw event and parse into a defined struct
# to be passed to the other handlers
def poc_parse_event(event: Any) -> Any:
    _event = event.split("||")
    str_event = str(_event[0])
    event_data = json.loads(_event[1]) if len(_event) > 1 else None

    return EventStruct(
        event_created=datetime.now(tz=timezone.utc),
        event_text=str_event,
        event_data=event_data,
        text_line_count=count_lines(str_event),
        raw_event=event,
    )


# This is to simulate calling a forwarding function for each event read
def poc_forwarder(event: Any):
    print(  # noqa: T201
        f"EVENT FORWARDED = {event.event_created}: {event.event_text}",
        flush=True,
    )


# Using a closure here to simulate wanting to isolate a particular connection.
# This could be used to select a connection by alias or clone a connection
# for long-rulling event streams.
def get_chunk_writer(connection, job_id: Any, job_created: datetime):
    def write_event_chunk(
        chunk_meta: "EventConsumer.ChunkMeta", chunk_data: List[EventStruct]
    ):
        _write_event_chunk(
            connection, job_id, job_created, chunk_meta, chunk_data
        )

    return write_event_chunk


# This is the actual chunk writer. It is responsible for collecting all of
# the event text into a single chunk of text and writing that to the event
# text table.
# It is also responsible for writing any associated data to the event data
# table.
def _write_event_chunk(
    connection,
    job_id: Any,
    job_created: datetime,
    chunk_meta: "EventConsumer.ChunkMeta",
    chunk_data: List[EventStruct],
):
    jes = JobEventsStream(
        job_id=job_id,
        job_created=job_created,
        event_chunk_created=chunk_meta.chunk_created,
        event_chunk_num=chunk_meta.chunk_number,
        event_chunk_start_line=chunk_meta.stream_start_line,
        event_chunk_end_line=chunk_meta.stream_end_line,
        event_chunk_text="".join(c.event_text for c in chunk_data),
    )
    jes.save()

    # Collect event data into discrete records (if any exists).
    jes_data = [
        JobEventsStreamData(
            job_id=job_id,
            stream_chunk=jes,
            stream_chunk_line=c.event_data.get("text_line_number"),
            event_data=c.event_data,
        )
        for c in chunk_data
        if c.event_data
    ]

    if jes_data:
        JobEventsStreamData.objects.bulk_create(jes_data)

    # Automatically commit on every 10 writes
    # This is here only as an illustration of what can be done by tracking
    # the chunk number.
    if chunk_meta.chunk_number % 10 == 0:
        connection.commit()


# This is to simulate reading from a subprocess or docker log.
def event_emitter():
    num_para = FAKE.random_int(10, 100)
    for i in range(num_para):
        event = FAKE.paragraphs()
        event_data = {
            "event_created": datetime.now(tz=timezone.utc),
            "event_number": i,
        }
        if i > 1:
            event.insert(0, os.linesep)
        yield "".join(event) + f"||{json.dumps(event_data, default=str)}"
        # Uncomment this to stop emitting event data with the event text.
        # yield ''.join(event)


def pretty_print_rec(recnum: int, inst: models.Model) -> str:
    longest_name = max(len(f.name) for f in inst._meta.concrete_fields)
    padding = longest_name + 2
    print(f"RECORD : {recnum: >5}")  # noqa: T201
    print("-" * 20)  # noqa: T201
    for f in inst._meta.concrete_fields:
        if isinstance(f, models.ForeignKey):
            ref_inst = getattr(inst, f)
            if ref_inst:
                value = ref_inst.pk
            else:
                value = None
        else:
            value = getattr(inst, f.name, None)
        print(f"  {f.name:{padding}}| {value}")  # noqa: T201
    print("", flush=True)  # noqa: T201


# ---------------------------------------------------
# ---------------------------------------------------

# Create the tables if they do not exist
create_table()


# Create our Django models for the PoC
class JobEventsStream(models.Model):
    class Meta:
        app_label = "core"
        db_table = "core_job_events_stream"

    id = models.UUIDField(primary_key=True, default=uuid4)
    job_id = models.UUIDField(null=False)
    job_created = models.DateTimeField(null=False)
    event_chunk_created = models.DateTimeField(null=False)
    event_chunk_num = models.BigIntegerField(null=False)
    event_chunk_start_line = models.BigIntegerField()
    event_chunk_end_line = models.BigIntegerField()
    event_chunk_text = models.TextField(null=False, default="")


class JobEventsStreamData(models.Model):
    class Meta:
        app_label = "core"
        db_table = "core_job_events_stream_data"

    id = models.UUIDField(primary_key=True, default=uuid4)
    job_id = models.UUIDField(null=False)
    stream_chunk = models.ForeignKey(
        "JobEventsStream", null=False, on_delete=models.DO_NOTHING
    )
    stream_chunk_line = models.BigIntegerField()
    event_data = models.JSONField()


# Instantiate the event consumer
consumer = EventConsumer(
    event_writer=get_chunk_writer(
        connection, uuid4(), datetime.now(tz=timezone.utc)
    ),
    #  Reader is always an iterable. This could be changed if needed.
    event_reader=iter(event_emitter()),
    event_parser=poc_parse_event,
    #  This is optional.
    event_forwarder=poc_forwarder,
    #  Change this to adjust how many chunks are written.
    chunk_size=1000,
)

# Run the consumer
consumer.consume()
connection.commit()

# Display counts
print(  # noqa: T201, E501
    f"{os.linesep}================================================="
)
print(f"Events consumed : {consumer.consumed_events: >5}")  # noqa: T201
print(f"Chunks written  : {consumer.chunks_written: >5}")  # noqa: T201
print(  # noqa: T201, E501
    f"================================================={os.linesep}"
)

# Get events stream records
# Some form of this query with or without pagination can be used to stream
# records.
# Writing in chunks is a little complicated, but reading the chunks is as
# simple as an ORM query.
print(f"{os.linesep}Table: {JobEventsStream._meta.db_table}")  # noqa: T201
for rec_num, rec in enumerate(
    JobEventsStream.objects.all().order_by("event_chunk_num")
):
    pretty_print_rec(rec_num + 1, rec)
