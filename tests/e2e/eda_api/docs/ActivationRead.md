# ActivationRead

Serializer for reading the Activation with related objects info.

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **int** |  | [readonly] 
**name** | **str** |  | 
**rulebook** | [**RulebookRef**](RulebookRef.md) |  | 
**instances** | [**[ActivationInstance]**](ActivationInstance.md) |  | 
**created_at** | **datetime** |  | [readonly] 
**modified_at** | **datetime** |  | [readonly] 
**description** | **str** |  | [optional] 
**is_enabled** | **bool** |  | [optional] 
**working_directory** | **str** |  | [optional] 
**execution_environment** | **str** |  | [optional] 
**project** | [**ProjectRef**](ProjectRef.md) |  | [optional] 
**extra_var** | [**ExtraVarRef**](ExtraVarRef.md) |  | [optional] 
**restart_policy** | [**RestartPolicyEnum**](RestartPolicyEnum.md) |  | [optional] 
**restart_count** | **int** |  | [optional] 
**any string name** | **bool, date, datetime, dict, float, int, list, str, none_type** | any string name can be used but the value must be the correct type | [optional]

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


