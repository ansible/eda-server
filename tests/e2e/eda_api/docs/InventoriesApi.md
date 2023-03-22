# eda_api.InventoriesApi

All URIs are relative to *<http://localhost>*

Method | HTTP request | Description
------------- | ------------- | -------------
[**create_inventory**](InventoriesApi.md#create_inventory) | **POST** /api/inventory | Create Inventory
[**delete_inventory**](InventoriesApi.md#delete_inventory) | **DELETE** /api/inventory/{inventory_id} | Delete Inventory
[**list_inventories**](InventoriesApi.md#list_inventories) | **GET** /api/inventories | List Inventories
[**read_inventory**](InventoriesApi.md#read_inventory) | **GET** /api/inventory/{inventory_id} | Read Inventory
[**update_inventory**](InventoriesApi.md#update_inventory) | **PATCH** /api/inventory/{inventory_id} | Update Inventory

# **create_inventory**
>
> InventoryRead create_inventory(inventory_create)

Create Inventory

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import inventories_api
from eda_api.model.inventory_read import InventoryRead
from eda_api.model.http_validation_error import HTTPValidationError
from eda_api.model.inventory_create import InventoryCreate
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: APIKeyCookie
configuration.api_key['APIKeyCookie'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['APIKeyCookie'] = 'Bearer'

# Configure OAuth2 access token for authorization: OAuth2PasswordBearer
configuration = eda_api.Configuration(
    host = "http://localhost"
)
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = inventories_api.InventoriesApi(api_client)
    inventory_create = InventoryCreate(
        name="name_example",
        description="",
        inventory="",
        inventory_source=None,
    ) # InventoryCreate |

    # example passing only required values which don't have defaults set
    try:
        # Create Inventory
        api_response = api_instance.create_inventory(inventory_create)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling InventoriesApi->create_inventory: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **inventory_create** | [**InventoryCreate**](InventoryCreate.md)|  |

### Return type

[**InventoryRead**](InventoryRead.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: application/json
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_inventory**
>
> delete_inventory(inventory_id)

Delete Inventory

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import inventories_api
from eda_api.model.http_validation_error import HTTPValidationError
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: APIKeyCookie
configuration.api_key['APIKeyCookie'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['APIKeyCookie'] = 'Bearer'

# Configure OAuth2 access token for authorization: OAuth2PasswordBearer
configuration = eda_api.Configuration(
    host = "http://localhost"
)
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = inventories_api.InventoriesApi(api_client)
    inventory_id = 1 # int |

    # example passing only required values which don't have defaults set
    try:
        # Delete Inventory
        api_instance.delete_inventory(inventory_id)
    except eda_api.ApiException as e:
        print("Exception when calling InventoriesApi->delete_inventory: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **inventory_id** | **int**|  |

### Return type

void (empty response body)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: Not defined
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**204** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_inventories**
>
> [InventoryRead] list_inventories()

List Inventories

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import inventories_api
from eda_api.model.inventory_read import InventoryRead
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: APIKeyCookie
configuration.api_key['APIKeyCookie'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['APIKeyCookie'] = 'Bearer'

# Configure OAuth2 access token for authorization: OAuth2PasswordBearer
configuration = eda_api.Configuration(
    host = "http://localhost"
)
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = inventories_api.InventoriesApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # List Inventories
        api_response = api_instance.list_inventories()
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling InventoriesApi->list_inventories: %s\n" % e)
```

### Parameters

This endpoint does not need any parameter.

### Return type

[**[InventoryRead]**](InventoryRead.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: Not defined
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **read_inventory**
>
> InventoryRead read_inventory(inventory_id)

Read Inventory

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import inventories_api
from eda_api.model.inventory_read import InventoryRead
from eda_api.model.http_validation_error import HTTPValidationError
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: APIKeyCookie
configuration.api_key['APIKeyCookie'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['APIKeyCookie'] = 'Bearer'

# Configure OAuth2 access token for authorization: OAuth2PasswordBearer
configuration = eda_api.Configuration(
    host = "http://localhost"
)
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = inventories_api.InventoriesApi(api_client)
    inventory_id = 1 # int |

    # example passing only required values which don't have defaults set
    try:
        # Read Inventory
        api_response = api_instance.read_inventory(inventory_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling InventoriesApi->read_inventory: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **inventory_id** | **int**|  |

### Return type

[**InventoryRead**](InventoryRead.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: Not defined
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_inventory**
>
> InventoryRead update_inventory(inventory_id, inventory_update)

Update Inventory

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import inventories_api
from eda_api.model.inventory_read import InventoryRead
from eda_api.model.http_validation_error import HTTPValidationError
from eda_api.model.inventory_update import InventoryUpdate
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure API key authorization: APIKeyCookie
configuration.api_key['APIKeyCookie'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['APIKeyCookie'] = 'Bearer'

# Configure OAuth2 access token for authorization: OAuth2PasswordBearer
configuration = eda_api.Configuration(
    host = "http://localhost"
)
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = inventories_api.InventoriesApi(api_client)
    inventory_id = 1 # int |
    inventory_update = InventoryUpdate(
        name="name_example",
        description="",
        inventory="",
    ) # InventoryUpdate |

    # example passing only required values which don't have defaults set
    try:
        # Update Inventory
        api_response = api_instance.update_inventory(inventory_id, inventory_update)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling InventoriesApi->update_inventory: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **inventory_id** | **int**|  |
 **inventory_update** | [**InventoryUpdate**](InventoryUpdate.md)|  |

### Return type

[**InventoryRead**](InventoryRead.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: application/json
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)
