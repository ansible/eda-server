# eda_api.AuditRulesApi

All URIs are relative to *<http://localhost>*

Method | HTTP request | Description
------------- | ------------- | -------------
[**list_audit_hosts_changed**](AuditRulesApi.md#list_audit_hosts_changed) | **GET** /api/audit/hosts_changed | List Audit Hosts Changed
[**list_audit_rule_events**](AuditRulesApi.md#list_audit_rule_events) | **GET** /api/audit/rule/{rule_id}/events | List Audit Rule Events
[**list_audit_rule_hosts**](AuditRulesApi.md#list_audit_rule_hosts) | **GET** /api/audit/rule/{rule_id}/hosts | List Audit Rule Hosts
[**list_audit_rule_jobs**](AuditRulesApi.md#list_audit_rule_jobs) | **GET** /api/audit/rule/{rule_id}/jobs | List Audit Rule Jobs
[**list_audit_rules_fired**](AuditRulesApi.md#list_audit_rules_fired) | **GET** /api/audit/rules_fired | List Audit Rules Fired
[**read_audit_rule_details**](AuditRulesApi.md#read_audit_rule_details) | **GET** /api/audit/rule/{rule_id}/details | Read Audit Rule Details

# **list_audit_hosts_changed**
>
> [AuditChangedHost] list_audit_hosts_changed()

List Audit Hosts Changed

### Example

```python
import time
import eda_api
from eda_api.api import audit_rules_api
from eda_api.model.audit_changed_host import AuditChangedHost
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with eda_api.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = audit_rules_api.AuditRulesApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # List Audit Hosts Changed
        api_response = api_instance.list_audit_hosts_changed()
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling AuditRulesApi->list_audit_hosts_changed: %s\n" % e)
```

### Parameters

This endpoint does not need any parameter.

### Return type

[**[AuditChangedHost]**](AuditChangedHost.md)

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

# **list_audit_rule_events**
>
> [AuditRuleJobInstanceEvent] list_audit_rule_events(rule_id)

List Audit Rule Events

### Example

- Api Key Authentication (APIKeyCookie):
- OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import audit_rules_api
from eda_api.model.audit_rule_job_instance_event import AuditRuleJobInstanceEvent
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
    api_instance = audit_rules_api.AuditRulesApi(api_client)
    rule_id = 1 # int |

    # example passing only required values which don't have defaults set
    try:
        # List Audit Rule Events
        api_response = api_instance.list_audit_rule_events(rule_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling AuditRulesApi->list_audit_rule_events: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **rule_id** | **int**|  |

### Return type

[**[AuditRuleJobInstanceEvent]**](AuditRuleJobInstanceEvent.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_audit_rule_hosts**
>
> [AuditRuleHost] list_audit_rule_hosts(rule_id)

List Audit Rule Hosts

### Example

- Api Key Authentication (APIKeyCookie):
- OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import audit_rules_api
from eda_api.model.http_validation_error import HTTPValidationError
from eda_api.model.audit_rule_host import AuditRuleHost
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
    api_instance = audit_rules_api.AuditRulesApi(api_client)
    rule_id = 1 # int |

    # example passing only required values which don't have defaults set
    try:
        # List Audit Rule Hosts
        api_response = api_instance.list_audit_rule_hosts(rule_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling AuditRulesApi->list_audit_rule_hosts: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **rule_id** | **int**|  |

### Return type

[**[AuditRuleHost]**](AuditRuleHost.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_audit_rule_jobs**
>
> [AuditRuleJobInstance] list_audit_rule_jobs(rule_id)

List Audit Rule Jobs

### Example

- Api Key Authentication (APIKeyCookie):
- OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import audit_rules_api
from eda_api.model.audit_rule_job_instance import AuditRuleJobInstance
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
    api_instance = audit_rules_api.AuditRulesApi(api_client)
    rule_id = 1 # int |

    # example passing only required values which don't have defaults set
    try:
        # List Audit Rule Jobs
        api_response = api_instance.list_audit_rule_jobs(rule_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling AuditRulesApi->list_audit_rule_jobs: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **rule_id** | **int**|  |

### Return type

[**[AuditRuleJobInstance]**](AuditRuleJobInstance.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **list_audit_rules_fired**
>
> [AuditFiredRule] list_audit_rules_fired()

List Audit Rules Fired

### Example

```python
import time
import eda_api
from eda_api.api import audit_rules_api
from eda_api.model.audit_fired_rule import AuditFiredRule
from pprint import pprint
# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = eda_api.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with eda_api.ApiClient() as api_client:
    # Create an instance of the API class
    api_instance = audit_rules_api.AuditRulesApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # List Audit Rules Fired
        api_response = api_instance.list_audit_rules_fired()
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling AuditRulesApi->list_audit_rules_fired: %s\n" % e)
```

### Parameters

This endpoint does not need any parameter.

### Return type

[**[AuditFiredRule]**](AuditFiredRule.md)

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

# **read_audit_rule_details**
>
> AuditRule read_audit_rule_details(rule_id)

Read Audit Rule Details

### Example

- Api Key Authentication (APIKeyCookie):
- OAuth Authentication (OAuth2PasswordBearer):

```python
import time
import eda_api
from eda_api.api import audit_rules_api
from eda_api.model.http_validation_error import HTTPValidationError
from eda_api.model.audit_rule import AuditRule
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
    api_instance = audit_rules_api.AuditRulesApi(api_client)
    rule_id = 1 # int |

    # example passing only required values which don't have defaults set
    try:
        # Read Audit Rule Details
        api_response = api_instance.read_audit_rule_details(rule_id)
        pprint(api_response)
    except eda_api.ApiException as e:
        print("Exception when calling AuditRulesApi->read_audit_rule_details: %s\n" % e)
```

### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **rule_id** | **int**|  |

### Return type

[**AuditRule**](AuditRule.md)

### Authorization

[APIKeyCookie](../README.md#APIKeyCookie), [OAuth2PasswordBearer](../README.md#OAuth2PasswordBearer)

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)
