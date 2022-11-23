

.PHONY: all models admin serializers views urls v2_api_access

all: tuples models admin serializers views urls v2_api_access

tuples:
	jinja2 codegen/tuples.pyt designs/models.yml > tuples.py
	black tuples.py

models:
	jinja2 codegen/models.pyt designs/models.yml > models.py
	black models.py

admin:
	jinja2 codegen/admin.pyt designs/models.yml > admin.py
	black admin.py

urls:
	jinja2 codegen/urls.pyt designs/models.yml > api_urls.py
	black api_urls.py

v2_api_access:
	jinja2 codegen/v2_api_access.pyt designs/models.yml > v2_api_access.py
	black v2_api_access.py

serializers:
	jinja2 codegen/serializers.pyt designs/models.yml > serializers.py
	black serializers.py

views:
	jinja2 codegen/views.pyt designs/models.yml > api_views.py
	black api_views.py
