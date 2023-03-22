# eda_api.DefaultApi

All URIs are relative to *<http://localhost>*

Method | HTTP request | Description
------------- | ------------- | -------------
[**ping_ping_get**](DefaultApi.md#ping_ping_get) | **GET** /ping | Ping
[**ssh_public_key_api_ssh_public_key_get**](DefaultApi.md#ssh_public_key_api_ssh_public_key_get) | **GET** /api/ssh-public-key | Ssh Public Key

# **ping_ping_get**
>
> bool, date, datetime, dict, float, int, list, str, none_type ping_ping_get()

Ping

### Example

```python
import time
import eda_api
from eda_api.api import default_api
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with eda_api.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = default_api.DefaultApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # Ping
        api_response = api_instance.ping_ping_get()
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling DefaultApi->ping_ping_get: %s\n" % e)
```

### Parameters

This endpoint does not need any parameter.

### Return type

**bool, date, datetime, dict, float, int, list, str, none_type**

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **ssh_public_key_api_ssh_public_key_get**
>
> bool, date, datetime, dict, float, int, list, str, none_type ssh_public_key_api_ssh_public_key_get()

Ssh Public Key

### Example

```python
import time
import eda_api
from eda_api.api import default_api
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with eda_api.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = default_api.DefaultApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # Ssh Public Key
        api_response = api_instance.ssh_public_key_api_ssh_public_key_get()
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling DefaultApi->ssh_public_key_api_ssh_public_key_get: %s\n" % e)
```

### Parameters

This endpoint does not need any parameter.

### Return type

**bool, date, datetime, dict, float, int, list, str, none_type**

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)
