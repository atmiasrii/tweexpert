"""Selector registry loader (E-06). No selector strings live anywhere else."""
from __future__ import annotations

from dataclasses import dataclass

import yaml

from ..config import get_settings


@dataclass
class SelectorEntry:
    key: str
    primary: str
    fallbacks: list[str]

    def all(self) -> list[str]:
        return [self.primary, *self.fallbacks]


class SelectorRegistry:
    def __init__(self, data: dict):
        self._data = data
        self.entries: dict[str, SelectorEntry] = {}
        for key, spec in data.get("selectors", {}).items():
            self.entries[key] = SelectorEntry(
                key=key,
                primary=spec["primary"],
                fallbacks=list(spec.get("fallbacks", [])),
            )
        self.surfaces: dict[str, dict] = data.get("surfaces", {})
        self.challenges: dict[str, list[str]] = data.get("challenges", {})

    def get(self, key: str) -> SelectorEntry:
        if key not in self.entries:
            raise KeyError(f"selector '{key}' not in registry")
        return self.entries[key]

    def keys(self) -> list[str]:
        return list(self.entries.keys())


_REGISTRY: SelectorRegistry | None = None


def load_registry(reload: bool = False) -> SelectorRegistry:
    global _REGISTRY
    if _REGISTRY is None or reload:
        path = get_settings().selectors_path
        with open(path, "r", encoding="utf-8") as f:
            _REGISTRY = SelectorRegistry(yaml.safe_load(f))
    return _REGISTRY
