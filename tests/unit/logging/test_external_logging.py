import pytest
from django.conf import settings
from django.test.utils import override_settings

from aap_eda.utils.external_logging import construct_rsyslog_conf_template

"""
# Example User Data
data_logstash = {
    "LOG_AGGREGATOR_TYPE": "logstash",
    "LOG_AGGREGATOR_HOST": "localhost",
    "LOG_AGGREGATOR_PORT": 8080,
    "LOG_AGGREGATOR_PROTOCOL": "tcp",
    "LOG_AGGREGATOR_USERNAME": "logger",
    "LOG_AGGREGATOR_PASSWORD": "mcstash"
}
data_netcat = {
    "LOG_AGGREGATOR_TYPE": "other",
    "LOG_AGGREGATOR_HOST": "localhost",
    "LOG_AGGREGATOR_PORT": 9000,
    "LOG_AGGREGATOR_PROTOCOL": "udp",
}
data_loggly = {
    "LOG_AGGREGATOR_TYPE": "loggly",
    "LOG_AGGREGATOR_HOST": "http://logs-01.loggly.com/inputs/1fd38090-2af1-4e1e-8d80-492899da0f71/tag/http/",
    "LOG_AGGREGATOR_PORT": 8080,
    "LOG_AGGREGATOR_PROTOCOL": "https"
}
"""  # noqa: E501


# Test reconfigure logging settings function
# name this whatever you want
@pytest.mark.parametrize(
    "enabled, log_type, host, port, protocol, errorfile, expected_config",
    [
        (
            True,
            "loggly",
            "http://logs-01.loggly.com/inputs/1fd38090-2af1-4e1e-8d80-492899da0f71/tag/http/",  # noqa: E501
            None,
            "https",
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="logs-01.loggly.com" serverport="80" usehttps="off" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="inputs/1fd38090-2af1-4e1e-8d80-492899da0f71/tag/http/")',  # noqa
                ]
            ),
        ),
        (
            True,  # localhost w/ custom UDP port
            "other",
            "localhost",
            9000,
            "udp",
            "",  # empty errorfile
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")',  # noqa
                    'action(type="omfwd" target="localhost" port="9000" protocol="udp" action.resumeRetryCount="-1" action.resumeInterval="5" template="eda" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5")',  # noqa
                ]
            ),
        ),
        (
            True,  # localhost w/ custom TCP port
            "other",
            "localhost",
            9000,
            "tcp",
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")',  # noqa
                    'action(type="omfwd" target="localhost" port="9000" protocol="tcp" action.resumeRetryCount="-1" action.resumeInterval="5" template="eda" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5")',  # noqa
                ]
            ),
        ),
        (
            True,  # https, default port 443
            "splunk",
            "https://yoursplunk/services/collector/event",
            None,
            None,
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="yoursplunk" serverport="443" usehttps="on" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="services/collector/event")',  # noqa
                ]
            ),
        ),
        (
            True,  # http, default port 80
            "splunk",
            "http://yoursplunk/services/collector/event",
            None,
            None,
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="yoursplunk" serverport="80" usehttps="off" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="services/collector/event")',  # noqa
                ]
            ),
        ),
        (
            True,  # https, custom port in URL string
            "splunk",
            "https://yoursplunk:8088/services/collector/event",
            None,
            None,
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="yoursplunk" serverport="8088" usehttps="on" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="services/collector/event")',  # noqa
                ]
            ),
        ),
        (
            True,  # https, custom port explicitly specified
            "splunk",
            "https://yoursplunk/services/collector/event",
            8088,
            None,
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="yoursplunk" serverport="8088" usehttps="on" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="services/collector/event")',  # noqa
                ]
            ),
        ),
        (
            True,  # no scheme specified in URL, default to https, respect custom port # noqa
            "splunk",
            "yoursplunk.org/services/collector/event",
            8088,
            "https",
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="yoursplunk.org" serverport="8088" usehttps="on" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="services/collector/event")',  # noqa
                ]
            ),
        ),
        (
            True,  # respect custom http-only port
            "splunk",
            "http://yoursplunk.org/services/collector/event",
            8088,
            None,
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="yoursplunk.org" serverport="8088" usehttps="off" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="services/collector/event")',  # noqa
                ]
            ),
        ),
        (
            True,  # valid sumologic config
            "sumologic",
            "https://endpoint5.collection.us2.sumologic.com/receiver/v1/http/ZaVnC4dhaV0qoiETY0MrM3wwLoDgO1jFgjOxE6-39qokkj3LGtOroZ8wNaN2M6DtgYrJZsmSi4-36_Up5TbbN_8hosYonLKHSSOSKY845LuLZBCBwStrHQ==",  # noqa
            None,
            "https",
            "/var/log/eda/rsyslog.err",
            "\n".join(
                [
                    'template(name="eda" type="string" string="%rawmsg-after-pri%")\nmodule(load="omhttp")',  # noqa
                    'action(type="omhttp" server="endpoint5.collection.us2.sumologic.com" serverport="443" usehttps="on" allowunsignedcerts="off" skipverifyhost="off" action.resumeRetryCount="-1" template="eda" action.resumeInterval="5" queue.spoolDirectory="/var/lib/eda" queue.filename="eda-external-logger-action-queue" queue.maxDiskSpace="1g" queue.maxFileSize="100m" queue.type="LinkedList" queue.saveOnShutdown="on" queue.syncqueuefiles="on" queue.checkpointInterval="1000" queue.size="131072" queue.highwaterMark="98304" queue.discardMark="117964" queue.discardSeverity="5" errorfile="/var/log/eda/rsyslog.err" restpath="receiver/v1/http/ZaVnC4dhaV0qoiETY0MrM3wwLoDgO1jFgjOxE6-39qokkj3LGtOroZ8wNaN2M6DtgYrJZsmSi4-36_Up5TbbN_8hosYonLKHSSOSKY845LuLZBCBwStrHQ==")',  # noqa
                ]
            ),
        ),
    ],
)
def test_rsyslog_conf_template(
    enabled, log_type, host, port, protocol, errorfile, expected_config, mocker
):
    # Set test settings
    logging_defaults = getattr(settings, "LOGGING")  # noqa: B009
    if port:
        with override_settings(
            LOGGING=logging_defaults,
            LOG_AGGREGATOR_ENABLED=enabled,
            LOG_AGGREGATOR_TYPE=log_type,
            LOG_AGGREGATOR_HOST=host,
            LOG_AGGREGATOR_RSYSLOGD_ERROR_LOG_FILE=errorfile,
            LOG_AGGREGATOR_PORT=port,
            LOG_AGGREGATOR_PROTOCOL=protocol,
            LOG_AGGREGATOR_VERIFY_CERT=True,
            LOG_AGGREGATOR_LOGGERS="aap, ansible_base, activity_stream",
            LOG_AGGREGATOR_USERNAME="",
            LOG_AGGREGATOR_PASSWORD="",
            LOG_AGGREGATOR_TCP_TIMEOUT=5,
            LOG_AGGREGATOR_LEVEL="WARNING",
            LOG_AGGREGATOR_ACTION_QUEUE_SIZE=131072,
            LOG_AGGREGATOR_ACTION_MAX_DISK_USAGE_GB=1,
            LOG_AGGREGATOR_MAX_DISK_USAGE_PATH="/var/lib/eda",
            LOG_AGGREGATOR_RSYSLOGD_DEBUG=False,
            MAX_EVENT_RES_DATA=700000,
        ):
            tmpl = construct_rsyslog_conf_template()
            assert expected_config in tmpl


def test_splunk_auth(mocker):
    logging_defaults = getattr(settings, "LOGGING")  # noqa: B009
    with override_settings(
        LOGGING=logging_defaults,
        LOG_AGGREGATOR_ENABLED=True,
        LOG_AGGREGATOR_TYPE="splunk",
        LOG_AGGREGATOR_HOST="example.org",
        LOG_AGGREGATOR_PASSWORD="SECRET-TOKEN",
        LOG_AGGREGATOR_PROTOCOL="https",
        LOG_AGGREGATOR_VERIFY_CERT=True,
    ):
        tmpl = construct_rsyslog_conf_template()
        assert (
            'httpheaderkey="Authorization" httpheadervalue="Splunk SECRET-TOKEN"'  # noqa
            in tmpl
        )
