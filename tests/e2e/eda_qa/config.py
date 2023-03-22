"""
Module for config management
"""
from typing import Optional
from typing import Union

import dynaconf

import eda_qa.utils as utils
from eda_qa.utils.fernet import decrypt

DEFAULT_CONFIG_FILE = f"{utils.CONFIG_PATH}/settings.yaml"


class Settings(dynaconf.LazySettings):
    """
    Dynaconf settings object extended to provide convenient values
    """

    @property
    def base_url(self):
        host = f"{self.http.host}"
        api_path = self.http.get("api_path", None) or ""
        if self.http.get("port", None):
            host = f"{self.http.host}:{self.http.port}"

        return f"{self.http.scheme}://{host}{api_path}"  # type: ignore comment;


def decrypt_values(
    data: Union[dict, list, Settings],
    password: Optional[str] = None,
):
    """
    Traverse all config object to find key:value with an encrypted value
    under the format: "!fernat:some-encrypted-string" and decrypt it
    """

    if isinstance(data, dict) or isinstance(data, Settings):
        for key, value in data.items():  # type: ignore comment;
            if isinstance(value, str) and value.startswith("!fernet:"):
                if password is None:
                    raise ValueError(
                        f"Wrong value for key: '{key}'. If a value is encrypted, the EDAQA_FERNET_PASSWORD environment variable must be defined",
                    )
                value = value.split(":")[1]
                data[key] = decrypt(data=value, key=password)

            if isinstance(value, dict) or isinstance(value, list):
                decrypt_values(value, password)

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) or isinstance(item, list):
                decrypt_values(item, password)


_config = Settings(
    env="default",
    environments=True,
    load_dotenv=True,
    envvar_prefix="EDAQA",
    root_path=utils.CONFIG_PATH,
    settings_files=[DEFAULT_CONFIG_FILE],
    env_switcher="EDAQA_ENV",
)

fernet_password = _config.get("fernet_password", None)  # type: ignore comment;
decrypt_values(_config, fernet_password)

config = _config
