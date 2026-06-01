from unittest.mock import MagicMock, patch

import pytest

from aap_eda.services.pg_notify import PGNotify


@patch("aap_eda.services.pg_notify.psycopg")
def test_payload_with_dollar_quotes_is_parameterized(mock_psycopg):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    malicious_data = {"event": "test$$; DROP TABLE users; --"}
    notifier = PGNotify(
        dsn="postgresql://localhost/eda",
        channel="test_chan",
        data=malicious_data,
    )
    notifier()

    mock_cursor.execute.assert_called_once_with(
        "SELECT pg_notify(%s, %s)",
        ["test_chan", '{"event": "test$$; DROP TABLE users; --"}'],
    )


@patch("aap_eda.services.pg_notify.MAX_MESSAGE_LENGTH", 50)
@patch("aap_eda.services.pg_notify.psycopg")
def test_chunked_payload_with_dollar_quotes_is_parameterized(mock_psycopg):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    large_data = {"event": "A" * 100 + "$$; DROP TABLE users; --"}
    notifier = PGNotify(
        dsn="postgresql://localhost/eda", channel="test_chan", data=large_data
    )
    notifier()

    for call in mock_cursor.execute.call_args_list:
        sql, params = call[0]
        assert sql == "SELECT pg_notify(%s, %s)"
        assert params[0] == "test_chan"
        assert "$$" not in sql


@pytest.mark.parametrize(
    "malicious_value",
    [
        "test$$; DROP TABLE users; --",
        "O'Reilly",
        "'; DELETE FROM events; --",
        "$tag$; SELECT pg_sleep(10); $tag$",
    ],
)
@patch("aap_eda.services.pg_notify.psycopg")
def test_sql_metacharacters_are_parameterized(mock_psycopg, malicious_value):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(
        return_value=mock_cursor
    )
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg.connect.return_value = mock_conn

    data = {"event": malicious_value}
    notifier = PGNotify(
        dsn="postgresql://localhost/eda", channel="test_chan", data=data
    )
    notifier()

    sql, params = mock_cursor.execute.call_args[0]
    assert sql == "SELECT pg_notify(%s, %s)"
    assert malicious_value in params[1]
