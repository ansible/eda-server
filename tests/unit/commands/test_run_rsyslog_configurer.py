import os
import tempfile

import pytest
from django.core.management import CommandError, call_command

def test_run_rsyslog_configurer_success(mocker):
    os.environ["LOG_AGGREGATOR_RSYSLOGD_CONF_DIR"] = "/var/lib/eda/rsyslog"
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = mocker.patch("aap_eda.utils.external_logging.getattr", return_value=temp_dir)
        config_string = '$WorkDirectory /var/lib/eda/rsyslog'
        mocker.patch("aap_eda.utils.external_logging.construct_rsyslog_conf_template", return_value=config_string)
        supervisor_cmd = mocker.patch("aap_eda.utils.external_logging.supervisor_service_command")

        call_command("run_rsyslog_configurer")
        config_filepath = f'{config_dir()}/rsyslog.conf'

        assert os.path.isfile(config_filepath)

        with open(config_dir() + '/rsyslog.conf', 'r') as f:
            written_config = f.read()

        assert written_config == f"{config_string}\n"

        supervisor_cmd.assert_not_called()

def test_run_rsyslog_configurer_exception(mocker):
    expected_message = 'Unhandled Exception in reconfigure_rsyslog: Test Exception'
    with pytest.raises(CommandError) as e:
        mocker.patch("aap_eda.utils.external_logging.getattr", side_effect=RuntimeError("Test Exception"))
        call_command('run_rsyslog_configurer')
    assert expected_message in str(e.value)