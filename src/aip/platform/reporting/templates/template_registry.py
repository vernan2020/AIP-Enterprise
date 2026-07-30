from __future__ import annotations

from src.aip.platform.reporting.templates.template import Template


class TemplateRegistry:
    """Registry for template objects."""

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}

    def register(self, template: Template) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> Template:
        return self._templates[name]

    def names(self) -> tuple[str, ...]:
        return tuple(self._templates)
