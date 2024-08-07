#  Copyright 2024 Red Hat, Inc.
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
"""Module to perform PG Notify to send data to activations."""
import json
import logging
import uuid

import psycopg
import xxhash
from django.conf import settings

from aap_eda.core.exceptions import PGNotifyError

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = settings.MAX_PG_NOTIFY_MESSAGE_SIZE
MESSAGE_CHUNKED_UUID = "_message_chunked_uuid"
MESSAGE_CHUNK_COUNT = "_message_chunk_count"
MESSAGE_CHUNK_SEQUENCE = "_message_chunk_sequence"
MESSAGE_CHUNK = "_chunk"
MESSAGE_LENGTH = "_message_length"
MESSAGE_XX_HASH = "_message_xx_hash"


class PGNotify:
    """The PGNotify action sends an event to a PG Pub Sub Channel.

    Needs
    dsn https://www.postgresql.org/docs/current/libpq-connect.html
    #LIBPQ-CONNSTRING-KEYWORD-VALUE
    channel the channel name to send the notifies
    event
    """

    def __init__(self, dsn: str, channel: str, data: dict):
        self.dsn = dsn
        self.channel = channel
        self.data = data

    def __call__(self):
        try:
            with psycopg.connect(
                conninfo=self.dsn,
                autocommit=True,
            ) as conn:
                with conn.cursor() as cursor:
                    payload = json.dumps(self.data)
                    message_length = len(payload)
                    logger.debug("Message length %d", message_length)
                    if message_length >= MAX_MESSAGE_LENGTH:
                        xx_hash = xxhash.xxh32(
                            payload.encode("utf-8")
                        ).hexdigest()
                        logger.debug("Message length exceeds, will chunk")
                        message_uuid = str(uuid.uuid4())
                        number_of_chunks = (
                            int(message_length / MAX_MESSAGE_LENGTH) + 1
                        )
                        chunked = {
                            MESSAGE_CHUNKED_UUID: message_uuid,
                            MESSAGE_CHUNK_COUNT: number_of_chunks,
                            MESSAGE_LENGTH: message_length,
                            MESSAGE_XX_HASH: xx_hash,
                        }
                        logger.debug("Chunk info %s", message_uuid)
                        logger.debug("Number of chunks %d", number_of_chunks)
                        logger.debug("Total data size %d", message_length)
                        logger.debug("XX Hash %s", xx_hash)

                        sequence = 1
                        for i in range(0, message_length, MAX_MESSAGE_LENGTH):
                            chunked[MESSAGE_CHUNK] = payload[
                                i : i + MAX_MESSAGE_LENGTH
                            ]
                            chunked[MESSAGE_CHUNK_SEQUENCE] = sequence
                            sequence += 1

                            logger.debug(
                                "Chunked Length %d", len(json.dumps(chunked))
                            )
                            cursor.execute(
                                f"NOTIFY {self.channel}, "
                                f"$${json.dumps(chunked)}$$;"
                            )
                    else:
                        cursor.execute(
                            f"NOTIFY {self.channel}, $${payload}$$;"
                        )
        except psycopg.OperationalError as e:
            logger.error("PG Notify operational error %s", str(e))
            raise PGNotifyError() from e
