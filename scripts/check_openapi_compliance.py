#!/usr/bin/env python3
#  Copyright 2025 Red Hat, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# flake8: noqa
"""Improved script to check OpenAPI 3.x compliance for EDA API specification.

Addresses AAP-56230: Ensure EDA OpenAPI 3.x Specification Compliance

This version handles Django initialization properly and can generate and
validate spec files.

This script uses Task to run the Django management command for generating
the spec. A virtual environment with all dependencies installed is required
to run the script.

Usage:
    # Validate existing spec file
    python scripts/check_openapi_compliance.py --spec-file openapi.json

    # Generate and validate new spec
    python scripts/check_openapi_compliance.py --generate
"""

import argparse
import json
import os
import subprocess
import sys

import yaml


def setup_django_if_needed():
    """Set up Django environment if not already configured."""
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aap_eda.settings")

    if not os.environ.get("EDA_SECRET_KEY"):
        os.environ.setdefault("EDA_SECRET_KEY", "insecure-dev-key-for-testing")

    try:
        import django
        from django.conf import settings

        if not settings.configured:
            django.setup()
        return True
    except Exception as e:
        print(f"⚠ Django setup failed: {e}")
        return False


def check_drf_spectacular_version():
    """Check current drf-spectacular version and OpenAPI support."""
    try:
        import drf_spectacular

        version = drf_spectacular.__version__
        print(f"✓ drf-spectacular version: {version}")

        # Check OpenAPI version capabilities
        django_ready = setup_django_if_needed()
        if django_ready:
            try:
                # Check framework capabilities based on drf-spectacular version
                # from the imported drf_spectacular.__version__
                spectacular_version = version
                # Known version capabilities (based on drf-spectacular
                # release notes)
                if spectacular_version.startswith("0.26"):
                    print("✓ OpenAPI 3.0 support: Full (up to 3.0.3)")
                    print("⚠ OpenAPI 3.1 support: Not available")
                    print("⚠ OpenAPI 3.2 support: Not available")
                    print(
                        "  Note: drf-spectacular 0.26.x primarily "
                        "targets OpenAPI 3.0.3"
                    )
                elif spectacular_version.startswith("0.27"):
                    print("✓ OpenAPI 3.0 support: Full (up to 3.0.3)")
                    print("✓ OpenAPI 3.1 support: Improved (more features)")
                    print("⚠ OpenAPI 3.2 support: Not available")
                else:
                    # For newer or unknown versions, check what we can detect
                    print(
                        "⚠ OpenAPI 3.1+ support: Unknown "
                        "(newer framework version)"
                    )
                    print(
                        "⚠ OpenAPI 3.2+ support: Unknown "
                        "(newer framework version)"
                    )
                # Check if OPENAPI_VERSION setting is available
                try:
                    from django.conf import settings

                    spectacular_settings = getattr(
                        settings, "SPECTACULAR_SETTINGS", {}
                    )
                    if "OPENAPI_VERSION" in spectacular_settings:
                        configured_version = spectacular_settings[
                            "OPENAPI_VERSION"
                        ]
                        print(
                            f"✓ Configured OpenAPI version: "
                            f"{configured_version}"
                        )
                except Exception:
                    pass

            except Exception as e:
                print(f"⚠ Could not check OpenAPI version support: {e}")
                print("✓ Framework available but version check failed")
        else:
            print("✓ Framework available (Django configuration skipped)")
            print("⚠ OpenAPI version check requires Django setup")

        return True
    except ImportError as e:
        print(f"✗ Error importing drf-spectacular: {e}")
        return False


def validate_openapi_spec_format(spec_data):
    """Validate basic OpenAPI 3.x structure."""
    required_fields = ["openapi", "info", "paths"]

    for field in required_fields:
        if field not in spec_data:
            print(f"✗ Missing required field: {field}")
            return False

    # Check OpenAPI version
    openapi_version = spec_data.get("openapi", "")
    if not openapi_version.startswith("3."):
        print(f"✗ Invalid OpenAPI version: {openapi_version} (expected 3.x)")
        return False

    print(f"✓ Valid OpenAPI version: {openapi_version}")

    # Check info section
    info = spec_data.get("info", {})
    required_info_fields = ["title", "version"]
    for field in required_info_fields:
        if field not in info:
            print(f"✗ Missing required info field: {field}")
            return False

    print(f"✓ API Title: {info['title']}")
    print(f"✓ API Version: {info['version']}")

    return True


def discover_drf_endpoints():
    """Discover API endpoints from Django REST Framework router config."""
    # Fallback endpoint list - all known base endpoints
    fallback_base_endpoints = [
        "/activation-instances/",
        "/activations/",
        "/audit-rules/",
        "/credential-input-sources/",
        "/credential-types/",
        "/decision-environments/",
        "/eda-credentials/",
        "/event-streams/",
        "/external_event_stream/",
        "/organizations/",
        "/projects/",
        "/rulebooks/",
        "/teams/",
        "/users/",
        "/users/me/awx-tokens/",
    ]

    django_ready = setup_django_if_needed()
    if not django_ready:
        print("⚠ Django not available, using fallback endpoint list")
        return fallback_base_endpoints, []

    # Try to import the main API URLs to discover registered viewsets
    try:
        import importlib

        api_urls_module = importlib.import_module("aap_eda.api.urls")

        # Look for router in the module
        router = getattr(api_urls_module, "router", None)
        if router and hasattr(router, "registry"):
            base_endpoints = []
            nested_endpoints = []

            for prefix, _, _ in router.registry:
                # Add base endpoint
                base_endpoint = f"/{prefix}/"
                base_endpoints.append(base_endpoint)

                # Add standard detail endpoint for each base endpoint
                nested_endpoints.append(f"/{prefix}/{{id}}/")

            if base_endpoints:
                print(
                    f"✓ Discovered {len(base_endpoints)} base endpoints "
                    f"from router"
                )
                print(
                    f"✓ Discovered {len(nested_endpoints)} nested endpoints "
                    f"from viewset actions"
                )
                return sorted(set(base_endpoints)), sorted(
                    set(nested_endpoints)
                )

    except Exception as e:
        print(f"⚠ Could not discover endpoints from router: {e}")

    # Final fallback when router discovery fails
    print("⚠ Using fallback endpoint list")
    return fallback_base_endpoints, []


def check_endpoint_coverage(spec_data):
    """Check API endpoint coverage using dynamically discovered endpoints."""
    paths = spec_data.get("paths", {})
    endpoint_count = len(paths)

    print(f"✓ Total API endpoints: {endpoint_count}")

    # Separate spec endpoints into base and nested
    spec_base_endpoints = [p for p in paths.keys() if "{" not in p]
    spec_nested_endpoints = [p for p in paths.keys() if "{" in p]

    print(f"  - Base endpoints: {len(spec_base_endpoints)}")
    print(f"  - Nested endpoints: {len(spec_nested_endpoints)}")

    # Discover expected base endpoints from DRF configuration
    print("\nDiscovering expected endpoints from DRF configuration...")
    expected_base_endpoints, _ = discover_drf_endpoints()

    # Check base endpoints coverage
    print("\nBase endpoints coverage:")
    missing_base = []
    for endpoint in expected_base_endpoints:
        endpoint_found = any(
            path.startswith(endpoint.rstrip("/"))
            or path == endpoint
            or path.endswith(endpoint)
            for path in spec_base_endpoints
        )
        if not endpoint_found:
            missing_base.append(endpoint)

    if missing_base:
        print(
            f"⚠ Missing base endpoints ({len(missing_base)}): "
            f"{missing_base[:3]}{'...' if len(missing_base) > 3 else ''}"
        )
    else:
        print("✓ All expected base endpoints present")

    base_coverage = (
        (
            (len(expected_base_endpoints) - len(missing_base))
            / len(expected_base_endpoints)
            * 100
        )
        if expected_base_endpoints
        else 100
    )
    print(
        f"✓ Base coverage: {base_coverage:.1f}% "
        f"({len(expected_base_endpoints) - len(missing_base)}/"
        f"{len(expected_base_endpoints)})"
    )

    # Analyze nested endpoints from OpenAPI spec
    print("\nNested endpoints analysis:")

    # Group nested endpoints by their base path
    nested_by_base = {}
    for nested_path in spec_nested_endpoints:
        # Extract base path (everything before the first {id})
        parts = nested_path.split("/")
        base_parts = []
        for part in parts:
            if "{" in part and "}" in part:
                break
            base_parts.append(part)

        base_path = "/".join(base_parts) + "/"
        if base_path not in nested_by_base:
            nested_by_base[base_path] = []
        nested_by_base[base_path].append(nested_path)

    # Check that each DRF viewset has corresponding detail endpoints
    missing_detail_endpoints = []
    for base_endpoint in expected_base_endpoints:
        detail_endpoint = base_endpoint.rstrip("/") + "/{id}/"
        detail_found = any(
            _endpoints_match(detail_endpoint, path)
            for path in spec_nested_endpoints
        )
        if not detail_found:
            missing_detail_endpoints.append(detail_endpoint)

    if missing_detail_endpoints:
        print(
            f"⚠ Missing detail endpoints ({len(missing_detail_endpoints)}): "
            f"{missing_detail_endpoints[:3]}"
            f"{'...' if len(missing_detail_endpoints) > 3 else ''}"
        )
    else:
        print("✓ All expected detail endpoints present")

    # Show sample nested endpoints for each base path
    print("\nNested endpoints by base path:")
    for base_path in sorted(nested_by_base.keys()):
        nested_count = len(nested_by_base[base_path])
        sample_nested = nested_by_base[base_path][:2]
        print(f"  {base_path} → {nested_count} endpoints: {sample_nested}")

    # Overall coverage assessment
    detail_coverage = (
        (
            (len(expected_base_endpoints) - len(missing_detail_endpoints))
            / len(expected_base_endpoints)
            * 100
        )
        if expected_base_endpoints
        else 100
    )

    print(
        f"\n✓ Detail endpoint coverage: {detail_coverage:.1f}% "
        f"({len(expected_base_endpoints) - len(missing_detail_endpoints)}/"
        f"{len(expected_base_endpoints)})"
    )
    print(f"✓ Total nested endpoints found: {len(spec_nested_endpoints)}")

    return len(missing_base) == 0 and len(missing_detail_endpoints) == 0


def _endpoints_match(expected, actual):
    """Check if expected endpoint pattern matches actual endpoint."""
    # Normalize both endpoints
    expected_normalized = expected.strip("/")
    actual_normalized = actual.strip("/")

    # Direct match
    if expected_normalized == actual_normalized:
        return True

    # Pattern matching for parameters
    expected_parts = expected_normalized.split("/")
    actual_parts = actual_normalized.split("/")

    if len(expected_parts) != len(actual_parts):
        return False

    for exp_part, act_part in zip(expected_parts, actual_parts):
        # If expected part is a parameter placeholder, it should match
        if exp_part.startswith("{") and exp_part.endswith("}"):
            continue
        # Otherwise, parts should match exactly
        elif exp_part != act_part:
            return False

    return True


def validate_operation_schemas(spec_data):
    """Validate operation schemas and responses."""
    paths = spec_data.get("paths", {})
    issues = []

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                # Check for operation ID
                if "operationId" not in operation:
                    issues.append(
                        f"Missing operationId: {method.upper()} {path}"
                    )

                # Check for responses
                if "responses" not in operation:
                    issues.append(
                        f"Missing responses: {method.upper()} {path}"
                    )
                else:
                    responses = operation["responses"]
                    success_codes = ["200", "201", "202", "204"]
                    if not any(code in responses for code in success_codes):
                        issues.append(
                            f"Missing success response: {method.upper()} "
                            f"{path}"
                        )

    if issues:
        print(f"⚠ Schema validation issues found ({len(issues)}):")
        for issue in issues[:10]:  # Show first 10 issues
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
        return False

    print("✓ All operations have required schemas")
    return True


def generate_openapi_spec(
    output_file="openapi.json", format_type="openapi-json"
):
    """Generate OpenAPI spec using Django management command."""
    print(f"Generating OpenAPI spec to {output_file}...")

    # Set up environment
    env = os.environ.copy()
    env.setdefault("EDA_SECRET_KEY", "insecure-dev-key-for-testing")

    try:
        # Use task manage command if available
        cmd = [
            "task",
            "manage",
            "--",
            "spectacular",
            "--color",
            "--file",
            output_file,
            "--format",
            format_type,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode == 0:
            print(f"✓ Successfully generated {output_file}")
            return True
        else:
            print(f"✗ Failed to generate spec: {result.stderr}")
            return False

    except FileNotFoundError:
        print(
            "⚠ 'task' command not found, trying direct "
            "poetry/manage.py approach"
        )
        try:
            # Try direct poetry approach
            cmd = [
                "poetry",
                "run",
                "aap-eda-manage",
                "spectacular",
                "--color",
                "--file",
                output_file,
                "--format",
                format_type,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, env=env
            )

            if result.returncode == 0:
                print(f"✓ Successfully generated {output_file}")
                return True
            else:
                print(f"✗ Failed to generate spec: {result.stderr}")
                return False
        except Exception as e:
            print(f"✗ Could not generate spec: {e}")
            return False


def load_spec_file(file_path):
    """Load OpenAPI spec from file (JSON or YAML)."""
    try:
        with open(file_path, "r") as f:
            if file_path.endswith(".json"):
                return json.load(f)
            else:
                return yaml.safe_load(f)
    except Exception as e:
        print(f"✗ Failed to load spec file {file_path}: {e}")
        return 1


def main():
    """Run main compliance check function."""
    parser = argparse.ArgumentParser(
        description="Check OpenAPI 3.x compliance for EDA API specification"
    )
    parser.add_argument(
        "--spec-file", help="Path to existing OpenAPI spec file to validate"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate new OpenAPI spec before validation",
    )
    parser.add_argument(
        "--output",
        default="openapi.json",
        help="Output file for generated spec (default: openapi.json)",
    )
    parser.add_argument(
        "--format",
        choices=["openapi-json", "openapi"],
        default="openapi-json",
        help="Output format (default: openapi-json)",
    )

    args = parser.parse_args()

    print("=== EDA OpenAPI 3.x Compliance Check ===")

    # Check 1: Framework version support
    print("1. Checking drf-spectacular framework support:")
    if not check_drf_spectacular_version():
        return 1

    # Check 2: Generate spec if requested
    if args.generate:
        print("\n2. Generating OpenAPI specification:")
        if not generate_openapi_spec(args.output, args.format):
            print("⚠ Generation failed, exiting...")
            return 1

        args.spec_file = args.output

    # Check 3: Validate existing spec file
    if args.spec_file:
        print(f"\n3. Validating OpenAPI specification: {args.spec_file}")
        spec_data = load_spec_file(args.spec_file)

        if spec_data:
            print("\n3a. Format validation:")
            format_valid = validate_openapi_spec_format(spec_data)

            print("\n3b. Endpoint coverage:")
            coverage_valid = check_endpoint_coverage(spec_data)

            print("\n3c. Operation schemas:")
            schema_valid = validate_operation_schemas(spec_data)

            print("\n=== Validation Summary ===")
            print(
                f"Format validation: {'✓ PASS' if format_valid else '✗ FAIL'}"
            )
            print(
                f"Endpoint coverage: "
                f"{'✓ PASS' if coverage_valid else '⚠ WARNINGS'}"
            )
            print(
                f"Schema validation: "
                f"{'✓ PASS' if schema_valid else '⚠ WARNINGS'}"
            )

            if not (format_valid and coverage_valid and schema_valid):
                print("\n⚠ Some issues found - see details above")
            else:
                print("\n✓ All validations passed!")
        else:
            return 1
    else:
        print("\n2. No spec file provided for validation")
        print("   Use --spec-file to validate an existing spec")
        print("   Use --generate to create and validate a new spec")

    return 0


if __name__ == "__main__":
    sys.exit(main())
