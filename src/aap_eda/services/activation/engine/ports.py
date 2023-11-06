import contextlib

import yaml


def find_ports(rulebook_text: str) -> list[tuple]:
    """
    Return (host, port) pairs for all sources in a rulebook.

    Walk the rulebook and find ports in source parameters
    Assume the rulebook is valid if it imported
    """
    rulebook = yaml.safe_load(rulebook_text)

    # Make a list of host, port pairs found in all sources in
    # rulesets in a rulebook
    found_ports = []

    # Walk all rulesets in a rulebook
    for ruleset in rulebook:
        # Walk through all sources in a ruleset
        for source in ruleset.get("sources", []):
            # Remove name from source
            if "name" in source:
                del source["name"]
            # The first remaining key is the type and the arguments
            source_plugin = list(source.keys())[0]
            source_args = source[source_plugin]
            if source_args is None:
                continue
            # Get host if it exists
            # Maybe check for "0.0.0.0" in the future
            host = source_args.get("host")
            # Get port if it exists
            maybe_port = source_args.get("port")
            # port may be a string or an integer
            with contextlib.suppress(ValueError):
                found_ports.append((host, int(maybe_port)))

    return found_ports
