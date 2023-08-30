import typing as tp

import aap_eda.core.models as models
from aap_eda.core.exceptions import AwxTokenNotFound


def get_awx_token(user_id: tp.Union[int, str]) -> str:
    """
    Retrieve the first AWX token decrypted for the given user ID.

    Args:
        user_id (Union[int, str]): The ID or string representation of the user.

    Returns:
        str: The decrypted value of the AWX token.

    Raises:
        AwxTokenNotFound: If no AWX token is found for the given user ID.
    """
    awx_token = models.AwxToken.objects.filter(user_id=user_id).first()
    if awx_token is None:
        raise AwxTokenNotFound
    return awx_token.token.get_secret_value()
