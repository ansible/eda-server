# eda_api.RulebooksApi

All URIs are relative to *http://localhost:8000/api/eda/v1*

Method | HTTP request | Description
------------- | ------------- | -------------
[**rulebooks_create**](RulebooksApi.md#rulebooks_create) | **POST** /rulebooks/ | 
[**rulebooks_json_retrieve**](RulebooksApi.md#rulebooks_json_retrieve) | **GET** /rulebooks/{id}/json/ | 
[**rulebooks_list**](RulebooksApi.md#rulebooks_list) | **GET** /rulebooks/ | 
[**rulebooks_retrieve**](RulebooksApi.md#rulebooks_retrieve) | **GET** /rulebooks/{id}/ | 
[**rulebooks_rulesets_list**](RulebooksApi.md#rulebooks_rulesets_list) | **GET** /rulebooks/{id}/rulesets/ | 


# **rulebooks_create**
> Rulebook rulebooks_create(rulebook)



### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import rulebooks_api
from eda_api.model.rulebook import Rulebook
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
    api_instance = rulebooks_api.RulebooksApi(api_client)
    rulebook = Rulebook(
        name="name_example",
        description="",
        rulesets="rulesets_example",
        project=1,
    ) # Rulebook | 

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.rulebooks_create(rulebook)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RulebooksApi->rulebooks_create: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **rulebook** | [**Rulebook**](Rulebook.md)|  |

### Return type

[**Rulebook**](Rulebook.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: application/json, application/x-www-form-urlencoded, multipart/form-data
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** |  |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **rulebooks_json_retrieve**
> Rulebook rulebooks_json_retrieve(id)



Get the JSON format of a rulebook by its id

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import rulebooks_api
from eda_api.model.rulebook import Rulebook
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
    api_instance = rulebooks_api.RulebooksApi(api_client)
    id = 1 # int | A unique integer value identifying this rulebook.

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.rulebooks_json_retrieve(id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RulebooksApi->rulebooks_json_retrieve: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| A unique integer value identifying this rulebook. |

### Return type

[**Rulebook**](Rulebook.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** |  |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **rulebooks_list**
> PaginatedRulebookList rulebooks_list()



List all rulebooks

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import rulebooks_api
from eda_api.model.paginated_rulebook_list import PaginatedRulebookList
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
    api_instance = rulebooks_api.RulebooksApi(api_client)
    name = "name_example" # str | Filter by rulebook name. (optional)
    page = 1 # int | A page number within the paginated result set. (optional)
    page_size = 1 # int | Number of results to return per page. (optional)

    # example passing only required values which don't have defaults set
    # and optional values
    try:
        api_response = api_instance.rulebooks_list(name=name, page=page, page_size=page_size)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RulebooksApi->rulebooks_list: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **name** | **str**| Filter by rulebook name. | [optional]
 **page** | **int**| A page number within the paginated result set. | [optional]
 **page_size** | **int**| Number of results to return per page. | [optional]

### Return type

[**PaginatedRulebookList**](PaginatedRulebookList.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Return a list of rulebooks. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **rulebooks_retrieve**
> Rulebook rulebooks_retrieve(id)



Get the rulebook by its id

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import rulebooks_api
from eda_api.model.rulebook import Rulebook
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
    api_instance = rulebooks_api.RulebooksApi(api_client)
    id = 1 # int | A unique integer value identifying this rulebook.

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.rulebooks_retrieve(id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RulebooksApi->rulebooks_retrieve: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| A unique integer value identifying this rulebook. |

### Return type

[**Rulebook**](Rulebook.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Return the rulebook by its id. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **rulebooks_rulesets_list**
> PaginatedRulesetOutList rulebooks_rulesets_list(id)



Ruleset list of a rulebook by its id

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import rulebooks_api
from eda_api.model.paginated_ruleset_out_list import PaginatedRulesetOutList
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
    api_instance = rulebooks_api.RulebooksApi(api_client)
    id = 1 # int | A unique integer value identifying this rulebook.
    name = "name_example" # str | Filter by rulebook name. (optional)
    page = 1 # int | A page number within the paginated result set. (optional)
    page_size = 1 # int | Number of results to return per page. (optional)

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.rulebooks_rulesets_list(id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RulebooksApi->rulebooks_rulesets_list: %s\n" % e)

    # example passing only required values which don't have defaults set
    # and optional values
    try:
        api_response = api_instance.rulebooks_rulesets_list(id, name=name, page=page, page_size=page_size)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling RulebooksApi->rulebooks_rulesets_list: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| A unique integer value identifying this rulebook. |
 **name** | **str**| Filter by rulebook name. | [optional]
 **page** | **int**| A page number within the paginated result set. | [optional]
 **page_size** | **int**| Number of results to return per page. | [optional]

### Return type

[**PaginatedRulesetOutList**](PaginatedRulesetOutList.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** |  |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

