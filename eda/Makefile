

.PHONY: all models admin v2_api_serializers v2_api_views v2_api_urls v2_api_access

all: tuples models admin v2_api_serializers v2_api_views v2_api_urls v2_api_access

tuples:
	jinja2 codegen/tuples.pyt designs/models.yml > tuples.py
	black tuples.py

models:
	jinja2 codegen/models.pyt designs/models.yml > models.py
	black models.py

admin:
	jinja2 codegen/admin.pyt designs/models.yml > admin.py
	black admin.py

v2_api_urls:
	jinja2 codegen/v2_api_urls.pyt designs/models.yml > v2_api_urls.py
	black v2_api_urls.py

v2_api_access:
	jinja2 codegen/v2_api_access.pyt designs/models.yml > v2_api_access.py
	black v2_api_access.py

v2_api_serializers:
	jinja2 codegen/v2_api_serializers.pyt designs/models.yml > v2_api_serializers.py
	black v2_api_serializers.py

v2_api_views:
	jinja2 codegen/v2_api_views.pyt designs/models.yml > v2_api_views.py
	black v2_api_views.py
