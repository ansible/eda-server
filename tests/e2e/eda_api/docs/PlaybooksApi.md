# eda_api.PlaybooksApi

All URIs are relative to *http://localhost:8000/api/eda/v1*

Method | HTTP request | Description
------------- | ------------- | -------------
[**playbooks_list**](PlaybooksApi.md#playbooks_list) | **GET** /playbooks/ | 
[**playbooks_retrieve**](PlaybooksApi.md#playbooks_retrieve) | **GET** /playbooks/{id}/ | 


# **playbooks_list**
> PaginatedPlaybookList playbooks_list()



List all playbooks

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import playbooks_api
from eda_api.model.paginated_playbook_list import PaginatedPlaybookList
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
    api_instance = playbooks_api.PlaybooksApi(api_client)
    page = 1 # int | A page number within the paginated result set. (optional)
    page_size = 1 # int | Number of results to return per page. (optional)

    # example passing only required values which don't have defaults set
    # and optional values
    try:
        api_response = api_instance.playbooks_list(page=page, page_size=page_size)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling PlaybooksApi->playbooks_list: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **page** | **int**| A page number within the paginated result set. | [optional]
 **page_size** | **int**| Number of results to return per page. | [optional]

### Return type

[**PaginatedPlaybookList**](PaginatedPlaybookList.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Return a list of playbooks. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **playbooks_retrieve**
> Playbook playbooks_retrieve(id)



Get the playbook by its id

### Example

* Basic Authentication (basicAuth):
* Api Key Authentication (cookieAuth):

```python
import time
import eda_api
from eda_api.api import playbooks_api
from eda_api.model.playbook import Playbook
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
    api_instance = playbooks_api.PlaybooksApi(api_client)
    id = 1 # int | A unique integer value identifying this playbook.

    # example passing only required values which don't have defaults set
    try:
        api_response = api_instance.playbooks_retrieve(id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling PlaybooksApi->playbooks_retrieve: %s\n" % e)
```


### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **id** | **int**| A unique integer value identifying this playbook. |

### Return type

[**Playbook**](Playbook.md)

### Authorization

[basicAuth](../README.md#basicAuth), [cookieAuth](../README.md#cookieAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Return the playbook by its id. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

