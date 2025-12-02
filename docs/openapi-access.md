## EDA OpenAPI Specification: Access and Distribution

This guide explains how to access the Event-Driven Ansible (EDA) OpenAPI specification.

---

### How to access the OpenAPI spec:

There are a few options that can be more well-suited for your use case:

Accessing via a browser:
- Open the Swagger UI: `http://localhost:8000/api/eda/v1/docs/`
- Or Redoc: `http://localhost:8000/api/eda/v1/redoc/`

The generated spec file can be found at:
- As a JSON: `http://localhost:8000/api/eda/v1/openapi.json`
- As a YAML: `http://localhost:8000/api/eda/v1/openapi.yaml`

You can also generate the OpenAPI spec offline, without starting EDA:
```bash
python src/aap_eda/manage.py spectacular --file openapi.yaml
python src/aap_eda/manage.py spectacular --file openapi.json
```

You can easily check schema version at runtime:
```bash
curl -s http://localhost:8000/api/eda/v1/openapi.json | jq -r .info.version
```

**Notes**:
- Endpoints require authentication by default. See [Authentication](#authentication) below.
- For TLS with self-signed certs, use `-k`/`--insecure` for local testing tools (curl, HTTP clients, etc).

---

### Configuration notes
API prefix can be customized (default: `api/eda`). If changed, schema endpoints move accordingly.
The schema generator is configured via DRF Spectacular; relevant settings include:
- Title, `info.version`, path prefix trimming, and servers URL.
- Anonymous access can be enabled by adjusting REST Framework permissions if needed (although, not recommended for production).

---

### Authentication
By default, schema endpoints require authentication (standard API auth with RBAC).

Common ways to authenticate are:
- Basic auth (user:password)
- Session cookie (after logging in via the UI or session endpoint)
- Bearer token/JWT (when issued by your identity provider or access gateway)

Examples:
- Basic auth:
  ```bash
  curl -u admin:password \
    "http://localhost:8000/api/eda/v1/openapi.json" -o eda.json
  ```
- Bearer token:
  ```bash
  curl -H "Authorization: Bearer $TOKEN" \
    "https://localhost:8000/api/eda/v1/openapi.json" -o eda.json
  ```

---

### Versioning and update cadence
The OpenAPI `info.version` is set from the installed `aap-eda` package version.
Runtime schemas are generated dynamically from the running service; they reflect whatever version is deployed.
For upstream usage, there is no central public catalog of static EDA specs. If you need a stable reference:
- Export the spec from a known EDA version (e.g., the image or package version you deploy).
- Check the exported file into your own repository under a versioned path, for example:
  - `openapi/eda-<version>.json` or `openapi/eda-<version>.yaml`
- Use that pinned file for SDK generation, CI, and documentation.

Typical workflow when upgrading:
- Upgrade your EDA environment, export the new spec, and commit it
- Diff the new spec against your previously pinned version to identify changes
- Regenerate clients and run integration tests against the new spec

**Notes**:
- If you generate client code, pin to a specific spec version for reproducible builds.
- For integration testing, compare the live spec to your pinned spec snapshot to catch breaking changes early.

---

### Code examples

Use `curl` to quickly download the spec:
```bash
# basic auth
curl -u admin:password \
  "http://localhost:8000/api/eda/v1/openapi.json" -o eda.json

# with a bearer token
curl -H "Authorization: Bearer $TOKEN" \
  "https://localhost:8000/api/eda/v1/openapi.json" -o eda.json
```

Python (`requests`):
```python
import requests

base = "https://your-host"
headers = {"Authorization": f"Bearer {TOKEN}"}  # or use auth=('admin','password')
r = requests.get(f"{base}/api/eda/v1/openapi.json", headers=headers, timeout=30)
r.raise_for_status()
spec = r.json()
print(spec["info"]["title"], spec["info"]["version"])
```

Node.js (`fetch`):
```javascript
const base = "https://your-host";
const res = await fetch(`${base}/api/eda/v1/openapi.json`, {
  headers: { Authorization: `Bearer ${process.env.TOKEN}` },
});
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const spec = await res.json();
console.log(spec.info.title, spec.info.version);
```

Go (`net/http`):
```go
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
)

func main() {
	base := "https://your-host"
	req, _ := http.NewRequest("GET", base+"/api/eda/v1/openapi.json", nil)
	req.Header.Set("Authorization", "Bearer "+os.Getenv("TOKEN"))
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()
	var spec map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&spec); err != nil {
		panic(err)
	}
	info := spec["info"].(map[string]any)
	fmt.Println(info["title"], info["version"])
}
```

#### OpenAPI tooling
For Swagger UI/Redoc, open the runtime UI endpoints in a browser (see [How to access the OpenAPI spec](#how-to-access-the-openapi-spec)).

With OpenAPI Generator:
  ```bash
  openapi-generator version
  openapi-generator generate \
    -i http://localhost:8000/api/eda/v1/openapi.json \
    -g python \
    -o ./sdk-python
  ```
