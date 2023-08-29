import pytest

from aap_eda.core import models
from aap_eda.wsapi.consumers import AnsibleRulebookConsumer
from aap_eda.wsapi.exceptions import AwxTokenNotFound


@pytest.fixture
def activation_instance_mock(mocker):
    activation_instance_mock = mocker.Mock(activation=mocker.Mock(user_id=1))
    mocker.patch.object(
        models.ActivationInstance.objects,
        "get",
        return_value=activation_instance_mock,
    )
    mocker.patch.object(
        models.ActivationInstance.objects,
        "filter",
        return_value=mocker.Mock(first=lambda: activation_instance_mock),
    )


@pytest.fixture
def message_mock(mocker):
    return mocker.Mock(activation_id=1)


async def test_get_awx_token_exists(
    activation_instance_mock, mocker, message_mock
):
    awx_token_mock = mocker.Mock(
        token=mocker.Mock(get_secret_value=lambda: "secret")
    )

    mocker.patch.object(
        models.AwxToken.objects,
        "filter",
        return_value=mocker.Mock(first=lambda: awx_token_mock),
    )
    consumer = AnsibleRulebookConsumer()

    awx_token = await consumer.get_awx_token(message_mock)
    assert awx_token == "secret"


async def test_get_awx_token_not_found(
    activation_instance_mock, mocker, message_mock
):
    mocker.patch.object(
        models.AwxToken.objects,
        "filter",
        return_value=mocker.Mock(first=lambda: None),
    )

    consumer = AnsibleRulebookConsumer()

    with pytest.raises(AwxTokenNotFound):
        await consumer.get_awx_token(message_mock)


async def test_write_instance_log(activation_instance_mock, mocker):
    logger_mock = mocker.Mock()
    activation_logger_mock = mocker.Mock(write=logger_mock)
    mocker.patch(
        "aap_eda.wsapi.consumers.ActivationDbLogger",
        return_value=activation_logger_mock,
    )

    consumer = AnsibleRulebookConsumer()

    await consumer.write_instance_log(1, "Test log message")

    logger_mock.assert_called_once_with("Test log message", flush=True)
