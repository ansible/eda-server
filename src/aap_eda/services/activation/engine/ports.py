import contextlib
import logging

import yaml
from django.conf import settings
from jinja2.exceptions import SecurityError, UndefinedError

from aap_eda.core.utils.strings import _SANDBOXED_ENV
from aap_eda.services.activation import exceptions

LOGGER = logging.getLogger(__name__)


def render_string(value: str, context: dict) -> str:
    if "{{" in value and "}}" in value:
        return _SANDBOXED_ENV.from_string(value).render(context)

    return value


def find_ports(rulebook_text: str, context: dict = None) -> list[tuple]:
    """Return (host, port) pairs for all sources in a rulebook."""
    rulebook = yaml.safe_load(rulebook_text)
    found_ports = []
    for ruleset in rulebook:
        for source in ruleset.get("sources", []):
            result = _extract_port(source, context or {})
            if result is not None:
                found_ports.append(result)
    return found_ports


def _extract_port(source, context):
    """Extract a (host, port) pair from a single source."""
    if "name" in source:
        del source["name"]
    # The first remaining key is the type and the arguments
    source_plugin = next(iter(source))

    if source_plugin not in settings.SAFE_PLUGINS_FOR_PORT_FORWARD:
        return None

    source_args = source[source_plugin]
    if source_args is None:
        return None

    host = source_args.get("host")
    # port may be a string or an integer
    maybe_port = source_args.get("port")
    if maybe_port is None:
        return None

    try:
        maybe_port = render_string(str(maybe_port), context)
        with contextlib.suppress(ValueError):
            return (host, int(maybe_port))
        return None
    except ValueError as e:
        LOGGER.exception(f"find_ports error: {e}")
        raise exceptions.ActivationStartError(str(e))
    except (UndefinedError, SecurityError) as e:
        raise exceptions.ActivationStartError(str(e))
