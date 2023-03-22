# eda_api.RolesApi

All URIs are relative to *<http://localhost>*

Method | HTTP request | Description
------------- | ------------- | -------------
[**add_role_permission**](RolesApi.md#add_role_permission) | **POST** /api/roles/{role_id}/permissions | Add Role Permissions
[**create_role**](RolesApi.md#create_role) | **POST** /api/roles | Create Role
[**delete_role**](RolesApi.md#delete_role) | **DELETE** /api/roles/{role_id} | Delete Role
[**delete_role_permission**](RolesApi.md#delete_role_permission) | **DELETE** /api/roles/{role_id}/permissions/{permission_id} | Delete Role Permission
[**list_role_permissions**](RolesApi.md#list_role_permissions) | **GET** /api/roles/{role_id}/permissions | List Role Permissions
[**list_roles**](RolesApi.md#list_roles) | **GET** /api/roles | List Roles
[**show_role**](RolesApi.md#show_role) | **GET** /api/roles/{role_id} | Show Role

# **add_role_permission**
>
> RolePermissionRead add_role_permission(role_id, role_permission_create)

Add Role Permissions

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
from eda_api.model.role_permission_create import RolePermissionCreate
from eda_api.model.role_permission_read import RolePermissionRead
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
    api_instance = roles_api.RolesApi(api_client)
    role_id = "role_id_example" # str |
    role_permission_create = RolePermissionCreate(
        resource_type=ResourceType("activation"),
        action=Action("create"),
    ) # RolePermissionCreate |

    # example passing only required values which don't have defaults set
    try:
        # Add Role Permissions
        api_response = api_instance.add_role_permission(role_id, role_permission_create)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->add_role_permission: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **role_id** | **str**|  |
 **role_permission_create** | [**RolePermissionCreate**](RolePermissionCreate.md)|  |

### Return type

[**RolePermissionRead**](RolePermissionRead.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: application/json
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **create_role**
>
> RoleRead create_role(role_create)

Create Role

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
from eda_api.model.role_read import RoleRead
from eda_api.model.role_create import RoleCreate
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
    api_instance = roles_api.RolesApi(api_client)
    role_create = RoleCreate(
        name="name_example",
        description="",
        is_default=False,
    ) # RoleCreate |

    # example passing only required values which don't have defaults set
    try:
        # Create Role
        api_response = api_instance.create_role(role_create)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->create_role: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **role_create** | [**RoleCreate**](RoleCreate.md)|  |

### Return type

[**RoleRead**](RoleRead.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

* **Content-Type**: application/json
* **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **delete_role**
>
> delete_role(role_id)

Delete Role

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
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
    api_instance = roles_api.RolesApi(api_client)
    role_id = "role_id_example" # str |

    # example passing only required values which don't have defaults set
    try:
        # Delete Role
        api_instance.delete_role(role_id)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->delete_role: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **role_id** | **str**|  |

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

# **delete_role_permission**
>
> bool, date, datetime, dict, float, int, list, str, none_type delete_role_permission(role_id, permission_id)

Delete Role Permission

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
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
    api_instance = roles_api.RolesApi(api_client)
    role_id = "role_id_example" # str |
    permission_id = "permission_id_example" # str |

    # example passing only required values which don't have defaults set
    try:
        # Delete Role Permission
        api_response = api_instance.delete_role_permission(role_id, permission_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->delete_role_permission: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **role_id** | **str**|  |
 **permission_id** | **str**|  |

### Return type

**bool, date, datetime, dict, float, int, list, str, none_type**

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

# **list_role_permissions**
>
> [RolePermissionRead] list_role_permissions(role_id)

List Role Permissions

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
from eda_api.model.role_permission_read import RolePermissionRead
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
    api_instance = roles_api.RolesApi(api_client)
    role_id = "role_id_example" # str |

    # example passing only required values which don't have defaults set
    try:
        # List Role Permissions
        api_response = api_instance.list_role_permissions(role_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->list_role_permissions: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **role_id** | **str**|  |

### Return type

[**[RolePermissionRead]**](RolePermissionRead.md)

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

# **list_roles**
>
> [RoleRead] list_roles()

List Roles

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
from eda_api.model.role_read import RoleRead
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
    api_instance = roles_api.RolesApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # List Roles
        api_response = api_instance.list_roles()
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->list_roles: %s\n" % e)
```

### Parameters

This endpoint does not need any parameter.

### Return type

[**[RoleRead]**](RoleRead.md)

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

# **show_role**
>
> RoleRead show_role(role_id)

Show Role

### Example

* Api Key Authentication (APIKeyCookie):
* OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import roles_api
from eda_api.model.role_read import RoleRead
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
    api_instance = roles_api.RolesApi(api_client)
    role_id = "role_id_example" # str |

    # example passing only required values which don't have defaults set
    try:
        # Show Role
        api_response = api_instance.show_role(role_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RolesApi->show_role: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **role_id** | **str**|  |

### Return type

[**RoleRead**](RoleRead.md)

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
