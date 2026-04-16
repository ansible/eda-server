# AGENTS.md

## Getting Started - Required Reading

**Before proceeding with any work, please read these files in order:**

1. **README.md** - Project overview and setup instructions
2. **docs/development.md** - Development environment setup guide
3. **docs/contributing.md** - Contribution guidelines

## Project Overview

EDA Server (Event-Driven Ansible Controller) is a REST API application that provides event-driven automation capabilities. It manages rulebooks, activations, credentials, decision environments, and event streams.

**Key Technologies** (refer to `pyproject.toml` for specific package versions):
- Django + Django REST Framework
- Django Channels + Daphne (WebSocket support)
- PostgreSQL
- dispatcherd (PostgreSQL-based task queue)
- django-ansible-base (DAB) for RBAC, JWT auth, resource registry
- Poetry for dependency management
- Taskfile (task/go-task) for build automation
- pytest for testing

**Related Repositories:**
- `django-ansible-base` - Shared RBAC, JWT, and feature flag library used across the platform
- `ansible-rulebook` - Rulebook engine for event-driven automation
- `ansible-runner` - Ansible execution engine
- `dispatcherd` - PostgreSQL-based task dispatcher
- `eda-server-operator` - Kubernetes operator for production deployment

## Build and Test Commands

### Initial Setup

Check `pyproject.toml` for supported Python versions. Always use the most recent supported version.

```bash
# Install dependencies and pre-commit hooks
task dev:init

# Start PostgreSQL and Redis (required for tests)
task docker:up:minimal

# Run database migrations
task manage -- migrate

# Seed initial data
task manage -- create_initial_data

# Create admin superuser (admin/testpass)
task create:superuser

# Start API server
task run:api
```

### Running Tests

**IMPORTANT:** Tests require PostgreSQL to be running. Start it with `task docker:up:minimal` first.

```bash
# Run all tests (runs twice: normal + multithreaded)
task test

# Run a specific test module
task test -- tests/integration/api/test_activation.py

# Run a single test
task test -- tests/integration/api/test_activation.py::test_retrieve_activation

# Run tests with Docker
task docker -- run --rm eda-api python -m pytest

# Run with verbose output
task test -- tests/integration/api/test_activation.py -v
```

**Test Markers:**
- `@pytest.mark.multithreaded` - Tests that must run in a separate process (run automatically by `task test`)

**Test Configuration:**
- pytest config is in `pytest.ini`
- `asyncio_mode = auto` (pytest-asyncio)
- `DJANGO_SETTINGS_MODULE = aap_eda.settings.default`
- Tests live in `tests/integration/` and `tests/unit/`

### Linting and Formatting

```bash
# Run all linters
task lint

# Individual linters
task lint:black       # Code formatting check
task lint:isort       # Import sorting check
task lint:ruff        # Fast linter (E, F, D, TID rules)
task lint:flake8      # Traditional linting
task lint:migrations  # Django migration check

# Auto-format code
task format           # Runs isort + black
```

## Code Style Guidelines

**Pre-commit Hooks** (installed via `task dev:init`):
- **black**: Code formatting (line length: 79)
- **isort**: Import sorting (black profile, line length: 79)
- **ruff**: Fast linter
- **flake8**: Traditional linting with plugins

**Testing Conventions:**
- Integration tests go in `tests/integration/` mirroring the source structure (`api/`, `core/`, `services/`, `tasks/`, `wsapi/`)
- Unit tests go in `tests/unit/`
- Global fixtures are defined in `tests/conftest.py`
- API tests use DRF's `APIClient`
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Use `@pytest.mark.parametrize` for similar test cases

## Security Considerations

- **SonarCloud**: Code quality and security analysis integrated via CI
- **Codecov**: Coverage tracking
- **Credential Storage**: All credentials are encrypted (via Cryptography + GPG)
- **Authentication**: JWT-based via django-ansible-base
- **Pre-commit Hooks**: Always run to catch security and quality issues

### GitHub Actions Security
- **NEVER use user-controlled data directly in run blocks**
  - Always pass through environment variables (e.g., `github.event.pull_request.body`)
- **Bad:** `echo "${{ github.event.pull_request.body }}" > file.txt`
- **Good:** Use env block and reference variables:
  ```yaml
  env:
    PR_BODY: ${{ github.event.pull_request.body }}
  run: |
    printf '%s' "$PR_BODY" > file.txt
  ```

## Architecture & Patterns

### Project Structure
```
src/aap_eda/
├── api/                     # REST API layer (views, serializers, filters)
├── core/                    # Core business logic (models, migrations, enums)
│   ├── models/              # Django ORM models
│   ├── management/          # Django management commands
│   ├── migrations/          # Database migrations
│   ├── tasking/             # Task/job scheduling (dispatcherd)
│   └── utils/               # Helper utilities
├── services/                # Business logic services
│   ├── activation/          # Activation lifecycle management
│   │   └── engine/          # Execution engines (Kubernetes, Podman)
│   └── project/             # Project management
├── tasks/                   # Background task definitions
├── settings/                # Django settings (dynaconf-based)
├── wsapi/                   # WebSocket API (Channels consumers)
├── analytics/               # Analytics feature
├── middleware/               # Custom middleware
└── utils/                   # Utility modules

tests/
├── integration/             # Integration tests (require PostgreSQL)
│   ├── api/                 # REST API endpoint tests
│   ├── core/                # Core model and logic tests
│   ├── services/            # Business logic service tests
│   ├── tasks/               # Task/job tests
│   ├── wsapi/               # WebSocket tests
│   ├── management/          # Management command tests
│   ├── dab_rbac/            # RBAC and permission tests
│   └── analytics/           # Analytics feature tests
├── unit/                    # Unit tests
└── conftest.py              # Global test fixtures
```

### Service Layer Architecture
```
API Views → Serializers → Services → Models → ORM → PostgreSQL
                         ↓
                  Business Logic
                  (Activation, Project, etc.)
```

### Key Components
- **ActivationService** - Manages activation lifecycle (create, start, stop, restart)
- **ProjectService** - Manages project synchronization
- **Engine Layer** - Container execution backends (Kubernetes, Podman, local)
- **StatusManager** - Real-time activation status tracking
- **dispatcherd** - PostgreSQL-based task queue with DefaultWorker and ActivationWorker

### API Endpoints
- Base path: `/api/eda/v1/`
- Swagger UI: `/api/eda/v1/docs/`
- OpenAPI spec: `/api/eda/v1/openapi.json`
- Status endpoint: `/api/eda/v1/status`

### Configuration
- **Dynaconf-based settings** with environment variable prefix `EDA_`
- Settings file: `/etc/eda/settings.yaml` (configurable via `EDA_SETTINGS_FILE`)
- Feature flags via django-flags

### Git Workflow Patterns
- Squash related commits into logical units
- Use `git commit --amend` for iterative fixes
- Always give agent co-author credit in commits

### Pull Request Guidelines
- **PR titles SHOULD be prefixed with JIRA number**: `[AAP-1234] Description of changes`
- **PR descriptions MUST include agent co-author attribution** at the end:
  ```markdown
  ---
  **Note:** This PR was developed with assistance from Claude AI assistant.
  ```

### Common Gotchas
- Tests require PostgreSQL running (`task docker:up:minimal`)
- The `task test` command runs tests twice: once normal, once with `-m multithreaded`
- Settings use dynaconf - environment variables must be prefixed with `EDA_`
- Import errors for missing modules - check Poetry dependencies

### Debugging Methodology
- Always investigate root causes rather than applying quick fixes
- Use verbose pytest output (`-v`) for test debugging
- Check Django settings via `task manage -- shell` for configuration issues
- Prefer systematic debugging over quick hacks
- The API endpoint `/api/eda/v1/status` can be used for health checks

## Additional Resources

- **docs/development.md** - Complete development setup guide
- **docs/contributing.md** - Contribution guidelines
- **docs/deployment.md** - Production deployment options
- **docs/openapi-access.md** - API documentation and authentication
- **docs/mac_development.md** - macOS-specific setup

