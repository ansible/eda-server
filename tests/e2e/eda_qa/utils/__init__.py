import pkg_resources

from eda_qa.utils.http_client import get_http_client

DATA_PATH = pkg_resources.resource_filename("eda_qa", "data")
CONFIG_PATH = pkg_resources.resource_filename("eda_qa", "conf")


def get_data_path(path: str) -> str:
    """
    Returns the absolute path from the default test data path given a relative path
    """
    return DATA_PATH + path


http_client = get_http_client()
