"""
Organization config template loading and generation.

Provides template-based skeleton generation for `scc org init`.
Templates are bundled JSON files with placeholder substitutions.

Key functions:
- list_templates(): List available template names with descriptions
- load_template(): Load a template with variable substitutions
- render_template(): Generate JSON output for a template

Template naming convention:
- minimal: Minimal quickstart config
- teams: Multi-team with profiles
- strict: Strict security for regulated industries
- reference: Complete reference with all fields
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, cast

# ═══════════════════════════════════════════════════════════════════════════════
# Template Registry
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata about an available template.

    Attributes:
        name: Template identifier (e.g., "minimal", "teams").
        description: Human-readable description.
        level: Complexity level ("beginner", "intermediate", "advanced").
        use_case: Primary use case description.
    """

    name: str
    description: str
    level: str
    use_case: str


# Available templates with metadata
TEMPLATES: dict[str, TemplateInfo] = {
    "minimal": TemplateInfo(
        name="minimal",
        description="Minimal quickstart config",
        level="beginner",
        use_case="First-time setup, single team, sensible defaults",
    ),
    "teams": TemplateInfo(
        name="teams",
        description="Multi-team with profiles and delegation",
        level="intermediate",
        use_case="Organizations with multiple teams needing different configs",
    ),
    "strict": TemplateInfo(
        name="strict",
        description="Strict security for regulated industries",
        level="advanced",
        use_case="Financial, healthcare, or compliance-heavy environments",
    ),
    "reference": TemplateInfo(
        name="reference",
        description="Complete reference with all fields",
        level="reference",
        use_case="Documentation and learning all available options",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Template Loading
# ═══════════════════════════════════════════════════════════════════════════════


class TemplateNotFoundError(Exception):
    """Raised when a template name is not recognized."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"Unknown template '{name}'. Available templates: {', '.join(sorted(available))}"
        )


def list_templates() -> list[TemplateInfo]:
    """List all available templates with metadata.

    Returns:
        List of TemplateInfo objects describing each template.

    Example:
        >>> templates = list_templates()
        >>> templates[0].name
        'minimal'
    """
    return list(TEMPLATES.values())


def get_template_info(name: str) -> TemplateInfo:
    """Get metadata for a specific template.

    Args:
        name: Template identifier.

    Returns:
        TemplateInfo for the requested template.

    Raises:
        TemplateNotFoundError: If template name is not recognized.
    """
    if name not in TEMPLATES:
        raise TemplateNotFoundError(name, list(TEMPLATES.keys()))
    return TEMPLATES[name]


def load_template_raw(name: str) -> str:
    """Load raw template content from package resources.

    Args:
        name: Template identifier (e.g., "minimal", "teams").

    Returns:
        Raw template content as string (with placeholders).

    Raises:
        TemplateNotFoundError: If template name is not recognized.
        FileNotFoundError: If template file doesn't exist.
    """
    # Validate template name exists
    if name not in TEMPLATES:
        raise TemplateNotFoundError(name, list(TEMPLATES.keys()))

    # Load from package resources
    template_file = files("scc_cli.templates.org").joinpath(f"{name}.json")
    try:
        return template_file.read_text()
    except FileNotFoundError:
        raise FileNotFoundError(f"Template file '{name}.json' not found in package")


# ═══════════════════════════════════════════════════════════════════════════════
# Template Rendering
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TemplateVars:
    """Variables for template substitution.

    Attributes:
        org_name: Organization name (e.g., "acme-corp").
        org_domain: Organization domain (e.g., "acme.com").
        schema_version: Schema version (default: "1.0.0").
        min_cli_version: Minimum CLI version (default: "1.2.0").
    """

    org_name: str = "my-org"
    org_domain: str = "example.com"
    schema_version: str = "1.0.0"
    min_cli_version: str = "1.2.0"


def render_template(
    name: str,
    vars: TemplateVars | None = None,
) -> dict[str, Any]:
    """Render a template with variable substitutions.

    Template placeholders use the format {{VAR_NAME}}.
    Supported placeholders:
    - {{ORG_NAME}}: Organization name
    - {{ORG_DOMAIN}}: Organization domain
    - {{SCHEMA_VERSION}}: Schema version
    - {{MIN_CLI_VERSION}}: Minimum CLI version

    Args:
        name: Template identifier.
        vars: Template variables for substitution.

    Returns:
        Rendered template as a dict.

    Raises:
        TemplateNotFoundError: If template name is not recognized.
        json.JSONDecodeError: If rendered template is not valid JSON.

    Example:
        >>> result = render_template("minimal", TemplateVars(org_name="acme"))
        >>> result["name"]
        'acme'
    """
    if vars is None:
        vars = TemplateVars()

    # Load raw template
    raw = load_template_raw(name)

    # Apply substitutions
    substitutions = {
        "{{ORG_NAME}}": vars.org_name,
        "{{ORG_DOMAIN}}": vars.org_domain,
        "{{SCHEMA_VERSION}}": vars.schema_version,
        "{{MIN_CLI_VERSION}}": vars.min_cli_version,
    }

    rendered = raw
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, value)

    # Parse as JSON
    return cast(dict[str, Any], json.loads(rendered))


def render_template_string(
    name: str,
    vars: TemplateVars | None = None,
    indent: int = 2,
) -> str:
    """Render a template as a formatted JSON string.

    This is useful for --stdout output or file writing.

    Args:
        name: Template identifier.
        vars: Template variables for substitution.
        indent: JSON indentation level (default: 2).

    Returns:
        Formatted JSON string.

    Example:
        >>> output = render_template_string("minimal")
        >>> print(output)
        {
          "name": "my-org",
          ...
        }
    """
    data = render_template(name, vars)
    return json.dumps(data, indent=indent, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_template_name(name: str) -> None:
    """Validate that a template name is recognized.

    This is a strict validation that raises an error for unknown names.
    Use this before any operation that requires a valid template.

    Args:
        name: Template name to validate.

    Raises:
        TemplateNotFoundError: If template name is not recognized.
    """
    if name not in TEMPLATES:
        raise TemplateNotFoundError(name, list(TEMPLATES.keys()))
