import pytest

from aap_eda.core import models
from aap_eda.core.exceptions import AwxTokenNotFound
from aap_eda.core.utils.awx_token import get_awx_token
from aap_eda.wsapi.consumers import (
    get_user_id_from_instance_id,
    write_instance_log,
)


@pytest.fixture
def activation_instance_mock(mocker):
    activation_instance_mock = mocker.Mock(activation=mocker.Mock(user_id=73))
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
def awx_token(admin_user):
    return models.AwxToken.objects.create(
        user_id=admin_user.id, token="dummy_token"
    )


@pytest.mark.django_db
def test_get_awx_token_exists(awx_token):
    token = get_awx_token(awx_token.user_id)

    assert token == "dummy_token"


@pytest.mark.django_db
def test_get_awx_token_not_found(admin_user):
    with pytest.raises(AwxTokenNotFound):
        get_awx_token(admin_user.id)


async def test_write_instance_log(activation_instance_mock, mocker):
    logger_mock = mocker.Mock()
    activation_logger_mock = mocker.Mock(write=logger_mock)
    mocker.patch(
        "aap_eda.wsapi.consumers.ActivationDbLogger",
        return_value=activation_logger_mock,
    )

    await write_instance_log(1, "Test log message")

    logger_mock.assert_called_once_with("Test log message", flush=True)


async def test_get_user_id_from_instance_id(activation_instance_mock):
    user_id = await get_user_id_from_instance_id(1)
    assert user_id == 73


async def test_get_user_id_from_instance_id_not_found(mocker):
    with pytest.raises(models.ActivationInstance.DoesNotExist):
        with mocker.patch.object(
            models.ActivationInstance.objects,
            "get",
            side_effect=models.ActivationInstance.DoesNotExist,
        ):
            await get_user_id_from_instance_id(167)
