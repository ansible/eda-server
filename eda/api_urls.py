from django.urls import include, path

from eda.api_views import (
    ActivationInstanceJobInstanceList,
    ActivationInstanceJobInstanceDetail,
)
from eda.api_views import ActivationInstanceList, ActivationInstanceDetail
from eda.api_views import ExtraVarList, ExtraVarDetail
from eda.api_views import ProjectList, ProjectDetail
from eda.api_views import InventoryList, InventoryDetail
from eda.api_views import RulebookList, RulebookDetail
from eda.api_views import JobInstanceList, JobInstanceDetail
from eda.api_views import ActivationInstanceLogList, ActivationInstanceLogDetail
from eda.api_views import RuleList, RuleDetail
from eda.api_views import RulesetList, RulesetDetail
from eda.api_views import JobList, JobDetail
from eda.api_views import PlaybookList, PlaybookDetail
from eda.api_views import AuditRuleList, AuditRuleDetail
from eda.api_views import JobInstanceEventList, JobInstanceEventDetail
from eda.api_views import JobInstanceHostList, JobInstanceHostDetail
from eda.api_views import ActivationList, ActivationDetail
from eda.api_views import RoleList, RoleDetail
from eda.api_views import RolePermissionList, RolePermissionDetail
from eda.api_views import UserRoleList, UserRoleDetail
from eda.api_views import UserList, UserDetail


urlpatterns = []


urlpatterns += [
    path(
        "activationinstancejobinstance/",
        ActivationInstanceJobInstanceList.as_view(),
        name="eda_activationinstancejobinstance_list",
    ),
    path(
        "activationinstancejobinstance/<int:pk>/",
        ActivationInstanceJobInstanceDetail.as_view(),
        name="eda_activationinstancejobinstance_detail",
    ),
]

urlpatterns += [
    path(
        "activationinstance/",
        ActivationInstanceList.as_view(),
        name="eda_activationinstance_list",
    ),
    path(
        "activationinstance/<int:pk>/",
        ActivationInstanceDetail.as_view(),
        name="eda_activationinstance_detail",
    ),
]

urlpatterns += [
    path("extravar/", ExtraVarList.as_view(), name="eda_extravar_list"),
    path("extravar/<int:pk>/", ExtraVarDetail.as_view(), name="eda_extravar_detail"),
]

urlpatterns += [
    path("project/", ProjectList.as_view(), name="eda_project_list"),
    path("project/<int:pk>/", ProjectDetail.as_view(), name="eda_project_detail"),
]

urlpatterns += [
    path("inventory/", InventoryList.as_view(), name="eda_inventory_list"),
    path("inventory/<int:pk>/", InventoryDetail.as_view(), name="eda_inventory_detail"),
]

urlpatterns += [
    path("rulebook/", RulebookList.as_view(), name="eda_rulebook_list"),
    path("rulebook/<int:pk>/", RulebookDetail.as_view(), name="eda_rulebook_detail"),
]

urlpatterns += [
    path("jobinstance/", JobInstanceList.as_view(), name="eda_jobinstance_list"),
    path(
        "jobinstance/<int:pk>/",
        JobInstanceDetail.as_view(),
        name="eda_jobinstance_detail",
    ),
]

urlpatterns += [
    path(
        "activationinstancelog/",
        ActivationInstanceLogList.as_view(),
        name="eda_activationinstancelog_list",
    ),
    path(
        "activationinstancelog/<int:pk>/",
        ActivationInstanceLogDetail.as_view(),
        name="eda_activationinstancelog_detail",
    ),
]

urlpatterns += [
    path("rule/", RuleList.as_view(), name="eda_rule_list"),
    path("rule/<int:pk>/", RuleDetail.as_view(), name="eda_rule_detail"),
]

urlpatterns += [
    path("ruleset/", RulesetList.as_view(), name="eda_ruleset_list"),
    path("ruleset/<int:pk>/", RulesetDetail.as_view(), name="eda_ruleset_detail"),
]

urlpatterns += [
    path("job/", JobList.as_view(), name="eda_job_list"),
    path("job/<int:pk>/", JobDetail.as_view(), name="eda_job_detail"),
]

urlpatterns += [
    path("playbook/", PlaybookList.as_view(), name="eda_playbook_list"),
    path("playbook/<int:pk>/", PlaybookDetail.as_view(), name="eda_playbook_detail"),
]

urlpatterns += [
    path("auditrule/", AuditRuleList.as_view(), name="eda_auditrule_list"),
    path("auditrule/<int:pk>/", AuditRuleDetail.as_view(), name="eda_auditrule_detail"),
]

urlpatterns += [
    path(
        "jobinstanceevent/",
        JobInstanceEventList.as_view(),
        name="eda_jobinstanceevent_list",
    ),
    path(
        "jobinstanceevent/<int:pk>/",
        JobInstanceEventDetail.as_view(),
        name="eda_jobinstanceevent_detail",
    ),
]

urlpatterns += [
    path(
        "jobinstancehost/",
        JobInstanceHostList.as_view(),
        name="eda_jobinstancehost_list",
    ),
    path(
        "jobinstancehost/<int:pk>/",
        JobInstanceHostDetail.as_view(),
        name="eda_jobinstancehost_detail",
    ),
]

urlpatterns += [
    path("activation/", ActivationList.as_view(), name="eda_activation_list"),
    path(
        "activation/<int:pk>/", ActivationDetail.as_view(), name="eda_activation_detail"
    ),
]

urlpatterns += [
    path("role/", RoleList.as_view(), name="eda_role_list"),
    path("role/<int:pk>/", RoleDetail.as_view(), name="eda_role_detail"),
]

urlpatterns += [
    path(
        "rolepermission/", RolePermissionList.as_view(), name="eda_rolepermission_list"
    ),
    path(
        "rolepermission/<int:pk>/",
        RolePermissionDetail.as_view(),
        name="eda_rolepermission_detail",
    ),
]

urlpatterns += [
    path("userrole/", UserRoleList.as_view(), name="eda_userrole_list"),
    path("userrole/<int:pk>/", UserRoleDetail.as_view(), name="eda_userrole_detail"),
]

urlpatterns += [
    path("user/", UserList.as_view(), name="eda_user_list"),
    path("user/<int:pk>/", UserDetail.as_view(), name="eda_user_detail"),
]

__all__ = ["urlpatterns"]
