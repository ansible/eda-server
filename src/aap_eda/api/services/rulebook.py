from aap_eda.core import models


class RulebookService:
    """Services for Rulebooks."""

    def __init__(self, rulebook: models.Rulebook):
        self.rulebook = rulebook

    def insert_rulebook_related_data(self, rulebook_data: dict) -> None:
        expanded_sources = self.expand_ruleset_sources(rulebook_data)

        for ruleset_data in rulebook_data or []:
            ruleset = models.Ruleset.objects.create(
                name=ruleset_data["name"],
                rulebook_id=self.rulebook.id,
                sources=expanded_sources.get(ruleset_data["name"]),
            )
            for rule in ruleset_data["rules"] or []:
                models.Rule.objects.create(
                    name=rule["name"],
                    action=rule["action"],
                    ruleset_id=ruleset.id,
                )

    def expand_ruleset_sources(self, rulebook_data: dict) -> dict:
        expanded_ruleset_sources = {}
        if rulebook_data is not None:
            for ruleset_data in rulebook_data:
                xp_sources = []
                expanded_ruleset_sources[ruleset_data["name"]] = xp_sources
                for source in ruleset_data.get("sources") or []:
                    xp_src = {"name": "<unnamed>"}
                    for src_key, src_val in source.items():
                        if src_key == "name":
                            xp_src["name"] = src_val
                        else:
                            xp_src["type"] = src_key.split(".")[-1]
                            xp_src["source"] = src_key
                            xp_src["config"] = src_val
                    xp_sources.append(xp_src)

        return expanded_ruleset_sources

    # TODO: define when audit rules/rulesets are available
    def build_fired_stat(self, ruleset_data: dict) -> [dict]:
        return [{}]
