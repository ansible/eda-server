# eda_api.ExtraVarsApi

All URIs are relative to *http://localhost:8000/api/eda/v1*

Method | HTTP request | Description
------------- | ------------- | -------------
[**extra_vars_create**](ExtraVarsApi.md#extra_vars_create) | **POST** /extra-vars/ | 
[**extra_vars_list**](ExtraVarsApi.md#extra_vars_list) | **GET** /extra-vars/ | 
[**extra_vars_retrieve**](ExtraVarsApi.md#extra_vars_retrieve) | **GET** /extra-vars/{id}/ | 


# **extra_vars_create**
> ExtraVar extra_vars_create(extra_var)



Create an extra_var

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import extra_vars_api
from eda_api.model.extra_var import ExtraVar
from pprint import pprint
# Defining the host is optional and defaults to http://localhost:8000/api/eda/v1
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost:8000/api/eda/v1"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure HTTP basic authorization: basicAuth
configuration = eda_api.Configuration(
    username = 'YOUR_USERNAME',
    password = 'YOUR_PASSWORD'
)

# Configure API key authorization: cookieAuth
configuration.api_key['cookieAuth'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['cookieAuth'] = 'Bearer'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = extra_vars_api.ExtraVarsApi(api_client)
    extra_var = ExtraVar(
        name="name_example",
        extra_var="extra_var_example",
        project=1,
    ) # ExtraVar | 

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.extra_vars_create(extra_var)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling ExtraVarsApi->extra_vars_create: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **extra_var** | [**ExtraVar**](ExtraVar.md)|  |

### Return type

[**ExtraVar**](ExtraVar.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Return the created extra_var. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **extra_vars_list**
> PaginatedExtraVarList extra_vars_list()



List all extra_vars

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import extra_vars_api
from eda_api.model.paginated_extra_var_list import PaginatedExtraVarList
from pprint import pprint
# Defining the host is optional and defaults to http://localhost:8000/api/eda/v1
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost:8000/api/eda/v1"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure HTTP basic authorization: basicAuth
configuration = eda_api.Configuration(
    username = 'YOUR_USERNAME',
    password = 'YOUR_PASSWORD'
)

# Configure API key authorization: cookieAuth
configuration.api_key['cookieAuth'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['cookieAuth'] = 'Bearer'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = extra_vars_api.ExtraVarsApi(api_client)
    page = 1 # int | A page number within the paginated result set. (optional)
    page_size = 1 # int | Number of results to return per page. (optional)

    # example passing only required values which don't have defaults set
    # and optional values
    try:
        api_response = api_instance.extra_vars_list(page=page, page_size=page_size)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling ExtraVarsApi->extra_vars_list: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page** | **int**| A page number within the paginated result set. | [optional]
 **page_size** | **int**| Number of results to return per page. | [optional]

### Return type

[**PaginatedExtraVarList**](PaginatedExtraVarList.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Return a list of extra_vars. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **extra_vars_retrieve**
> ExtraVar extra_vars_retrieve(id)



Get the extra_var by its id

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import extra_vars_api
from eda_api.model.extra_var import ExtraVar
from pprint import pprint
# Defining the host is optional and defaults to http://localhost:8000/api/eda/v1
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost:8000/api/eda/v1"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure HTTP basic authorization: basicAuth
configuration = eda_api.Configuration(
    username = 'YOUR_USERNAME',
    password = 'YOUR_PASSWORD'
)

# Configure API key authorization: cookieAuth
configuration.api_key['cookieAuth'] = 'YOUR_API_KEY'

# Uncomment below to setup prefix (e.g. Bearer) for API key, if needed
# configuration.api_key_prefix['cookieAuth'] = 'Bearer'

# Enter a context with an instance of the API client
with eda_api.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = extra_vars_api.ExtraVarsApi(api_client)
    id = 1 # int | A unique integer value identifying this extra var.

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.extra_vars_retrieve(id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling ExtraVarsApi->extra_vars_retrieve: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| A unique integer value identifying this extra var. |

### Return type

[**ExtraVar**](ExtraVar.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Return the extra_var by its id. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

