from django.conf.urls import url

from eda.v2_api_views import AlembicVersionList, AlembicVersionDetail
from eda.v2_api_views import (
    ActivationInstanceJobInstanceList,
    ActivationInstanceJobInstanceDetail,
)
from eda.v2_api_views import ActivationInstanceList, ActivationInstanceDetail
from eda.v2_api_views import ExtraVarList, ExtraVarDetail
from eda.v2_api_views import ProjectList, ProjectDetail
from eda.v2_api_views import InventoryList, InventoryDetail
from eda.v2_api_views import RulebookList, RulebookDetail
from eda.v2_api_views import JobInstanceList, JobInstanceDetail
from eda.v2_api_views import ActivationInstanceLogList, ActivationInstanceLogDetail
from eda.v2_api_views import RuleList, RuleDetail
from eda.v2_api_views import RulesetList, RulesetDetail
from eda.v2_api_views import JobList, JobDetail
from eda.v2_api_views import PlaybookList, PlaybookDetail
from eda.v2_api_views import AuditRuleList, AuditRuleDetail
from eda.v2_api_views import JobInstanceEventList, JobInstanceEventDetail
from eda.v2_api_views import JobInstanceHostList, JobInstanceHostDetail
from eda.v2_api_views import ActivationList, ActivationDetail
from eda.v2_api_views import RoleList, RoleDetail
from eda.v2_api_views import RolePermissionList, RolePermissionDetail
from eda.v2_api_views import UserRoleList, UserRoleDetail
from eda.v2_api_views import UserList, UserDetail


urls = []


urls += [
    url(
        r"^alembicversion/$",
        AlembicVersionList.as_view(),
        name="canvas_alembicversion_list",
    ),
    url(
        r"^alembicversion/(?P<pk>[0-9]+)/$",
        AlembicVersionDetail.as_view(),
        name="canvas_alembicversion_detail",
    ),
]

urls += [
    url(
        r"^activationinstancejobinstance/$",
        ActivationInstanceJobInstanceList.as_view(),
        name="canvas_activationinstancejobinstance_list",
    ),
    url(
        r"^activationinstancejobinstance/(?P<pk>[0-9]+)/$",
        ActivationInstanceJobInstanceDetail.as_view(),
        name="canvas_activationinstancejobinstance_detail",
    ),
]

urls += [
    url(
        r"^activationinstance/$",
        ActivationInstanceList.as_view(),
        name="canvas_activationinstance_list",
    ),
    url(
        r"^activationinstance/(?P<pk>[0-9]+)/$",
        ActivationInstanceDetail.as_view(),
        name="canvas_activationinstance_detail",
    ),
]

urls += [
    url(r"^extravar/$", ExtraVarList.as_view(), name="canvas_extravar_list"),
    url(
        r"^extravar/(?P<pk>[0-9]+)/$",
        ExtraVarDetail.as_view(),
        name="canvas_extravar_detail",
    ),
]

urls += [
    url(r"^project/$", ProjectList.as_view(), name="canvas_project_list"),
    url(
        r"^project/(?P<pk>[0-9]+)/$",
        ProjectDetail.as_view(),
        name="canvas_project_detail",
    ),
]

urls += [
    url(r"^inventory/$", InventoryList.as_view(), name="canvas_inventory_list"),
    url(
        r"^inventory/(?P<pk>[0-9]+)/$",
        InventoryDetail.as_view(),
        name="canvas_inventory_detail",
    ),
]

urls += [
    url(r"^rulebook/$", RulebookList.as_view(), name="canvas_rulebook_list"),
    url(
        r"^rulebook/(?P<pk>[0-9]+)/$",
        RulebookDetail.as_view(),
        name="canvas_rulebook_detail",
    ),
]

urls += [
    url(r"^jobinstance/$", JobInstanceList.as_view(), name="canvas_jobinstance_list"),
    url(
        r"^jobinstance/(?P<pk>[0-9]+)/$",
        JobInstanceDetail.as_view(),
        name="canvas_jobinstance_detail",
    ),
]

urls += [
    url(
        r"^activationinstancelog/$",
        ActivationInstanceLogList.as_view(),
        name="canvas_activationinstancelog_list",
    ),
    url(
        r"^activationinstancelog/(?P<pk>[0-9]+)/$",
        ActivationInstanceLogDetail.as_view(),
        name="canvas_activationinstancelog_detail",
    ),
]

urls += [
    url(r"^rule/$", RuleList.as_view(), name="canvas_rule_list"),
    url(r"^rule/(?P<pk>[0-9]+)/$", RuleDetail.as_view(), name="canvas_rule_detail"),
]

urls += [
    url(r"^ruleset/$", RulesetList.as_view(), name="canvas_ruleset_list"),
    url(
        r"^ruleset/(?P<pk>[0-9]+)/$",
        RulesetDetail.as_view(),
        name="canvas_ruleset_detail",
    ),
]

urls += [
    url(r"^job/$", JobList.as_view(), name="canvas_job_list"),
    url(r"^job/(?P<pk>[0-9]+)/$", JobDetail.as_view(), name="canvas_job_detail"),
]

urls += [
    url(r"^playbook/$", PlaybookList.as_view(), name="canvas_playbook_list"),
    url(
        r"^playbook/(?P<pk>[0-9]+)/$",
        PlaybookDetail.as_view(),
        name="canvas_playbook_detail",
    ),
]

urls += [
    url(r"^auditrule/$", AuditRuleList.as_view(), name="canvas_auditrule_list"),
    url(
        r"^auditrule/(?P<pk>[0-9]+)/$",
        AuditRuleDetail.as_view(),
        name="canvas_auditrule_detail",
    ),
]

urls += [
    url(
        r"^jobinstanceevent/$",
        JobInstanceEventList.as_view(),
        name="canvas_jobinstanceevent_list",
    ),
    url(
        r"^jobinstanceevent/(?P<pk>[0-9]+)/$",
        JobInstanceEventDetail.as_view(),
        name="canvas_jobinstanceevent_detail",
    ),
]

urls += [
    url(
        r"^jobinstancehost/$",
        JobInstanceHostList.as_view(),
        name="canvas_jobinstancehost_list",
    ),
    url(
        r"^jobinstancehost/(?P<pk>[0-9]+)/$",
        JobInstanceHostDetail.as_view(),
        name="canvas_jobinstancehost_detail",
    ),
]

urls += [
    url(r"^activation/$", ActivationList.as_view(), name="canvas_activation_list"),
    url(
        r"^activation/(?P<pk>[0-9]+)/$",
        ActivationDetail.as_view(),
        name="canvas_activation_detail",
    ),
]

urls += [
    url(r"^role/$", RoleList.as_view(), name="canvas_role_list"),
    url(r"^role/(?P<pk>[0-9]+)/$", RoleDetail.as_view(), name="canvas_role_detail"),
]

urls += [
    url(
        r"^rolepermission/$",
        RolePermissionList.as_view(),
        name="canvas_rolepermission_list",
    ),
    url(
        r"^rolepermission/(?P<pk>[0-9]+)/$",
        RolePermissionDetail.as_view(),
        name="canvas_rolepermission_detail",
    ),
]

urls += [
    url(r"^userrole/$", UserRoleList.as_view(), name="canvas_userrole_list"),
    url(
        r"^userrole/(?P<pk>[0-9]+)/$",
        UserRoleDetail.as_view(),
        name="canvas_userrole_detail",
    ),
]

urls += [
    url(r"^user/$", UserList.as_view(), name="canvas_user_list"),
    url(r"^user/(?P<pk>[0-9]+)/$", UserDetail.as_view(), name="canvas_user_detail"),
]

__all__ = ["urls"]
