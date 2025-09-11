"""AutoRepro rules engine for command suggestion."""

import importlib.util
import logging
import os
import sys
from typing import NamedTuple


class Rule(NamedTuple):
    """A command rule with matching criteria and metadata."""

    cmd: str
    keywords: set[str]
    weight: int = 0
    tags: set[str] = set()


# Built-in rules organized by language/ecosystem
BUILTIN_RULES = {
    "python": [
        Rule("pytest", {"pytest"}, 0, {"test"}),
        Rule("pytest -q", {"pytest"}, 1, {"test"}),
        Rule("python -m pytest -q", {"pytest"}, 1, {"test"}),
        Rule("python -m unittest -v", {"unittest"}, 1, {"test"}),
        Rule("tox -e py311", {"tox"}, 1, {"test"}),
    ],
    "node": [
        Rule("npm test", {"npm test"}, 0, {"test"}),
        Rule("npm test -s", {"npm test"}, 1, {"test"}),
        Rule("pnpm test", {"pnpm test"}, 0, {"test"}),
        Rule("pnpm test -s", {"pnpm test"}, 1, {"test"}),
        Rule("yarn test", {"yarn test"}, 0, {"test"}),
        Rule("yarn test -s", {"yarn test"}, 1, {"test"}),
        Rule("npx jest", {"jest"}, 0, {"test"}),
        Rule("npx jest -w=1", {"jest"}, 1, {"test"}),
        Rule("npx vitest run", {"vitest"}, 1, {"test"}),
        Rule("npx mocha", {"mocha"}, 1, {"test"}),
        Rule("npx playwright test", {"playwright"}, 1, {"test"}),
        Rule("npx cypress run", {"cypress"}, 1, {"test"}),
    ],
    "go": [
        Rule("go test", {"go test"}, 0, {"test"}),
        Rule("go test ./... -run .", {"go test"}, 1, {"test"}),
        Rule("gotestsum", {"gotestsum"}, 1, {"test"}),
    ],
    "electron": [
        Rule("npx electron .", {"electron"}, 1, {"run"}),
    ],
    "rust": [
        Rule("cargo test", {"cargo test"}, 1, {"test"}),
    ],
    "java": [
        Rule("mvn -q -DskipITs test", {"mvn", "maven"}, 1, {"test"}),
        Rule("./gradlew test", {"gradle", "gradlew"}, 1, {"test"}),
    ],
}


def _get_plugin_list() -> list[str]:
    """
    Get list of plugins from environment variable.

    Returns:
        List of plugin names/paths, empty if none specified
    """
    plugins_env = os.environ.get("AUTOREPRO_PLUGINS")
    if not plugins_env:
        return []
    return [p.strip() for p in plugins_env.split(",") if p.strip()]


def _load_plugin_module(plugin_name: str) -> object:
    """
    Load a single plugin module.

    Args:
        plugin_name: Name or file path of plugin to load

    Returns:
        Loaded plugin module

    Raises:
        ImportError: If plugin cannot be loaded
    """
    if plugin_name.endswith(".py"):
        # Support direct file paths ending with .py
        spec = importlib.util.spec_from_file_location("plugin", plugin_name)
        if spec and spec.loader:
            plugin_module = importlib.util.module_from_spec(spec)
            sys.modules["plugin"] = plugin_module
            spec.loader.exec_module(plugin_module)
            return plugin_module
        else:
            raise ImportError(f"Could not load spec from {plugin_name}")
    else:
        return importlib.import_module(plugin_name)


def _extract_rules_from_module(
    plugin_module: object, plugin_rules: dict[str, list[Rule]]
) -> None:
    """
    Extract rules from a loaded plugin module.

    Args:
        plugin_module: Loaded plugin module
        plugin_rules: Dictionary to add rules to (modified in-place)
    """
    if hasattr(plugin_module, "provide_rules"):
        rules_dict = plugin_module.provide_rules()
        if isinstance(rules_dict, dict):
            for ecosystem, rules in rules_dict.items():
                if ecosystem not in plugin_rules:
                    plugin_rules[ecosystem] = []
                plugin_rules[ecosystem].extend(rules)


def _handle_plugin_loading_error(plugin_name: str, error: Exception) -> None:
    """
    Handle plugin loading errors with optional debug output.

    Args:
        plugin_name: Name of plugin that failed to load
        error: Exception that occurred
    """
    debug = os.environ.get("AUTOREPRO_PLUGINS_DEBUG") == "1"
    logger = logging.getLogger("autorepro.rules")
    if debug:
        logger.error(
            "Plugin loading failed",
            extra={"plugin": plugin_name, "error": str(error)},
        )


def _load_plugin_rules() -> dict[str, list[Rule]]:
    """Load rules from plugins specified in AUTOREPRO_PLUGINS environment variable."""
    plugin_rules: dict[str, list[Rule]] = {}
    plugins = _get_plugin_list()

    for plugin_name in plugins:
        try:
            plugin_module = _load_plugin_module(plugin_name)
            _extract_rules_from_module(plugin_module, plugin_rules)
        except Exception as e:
            _handle_plugin_loading_error(plugin_name, e)
            continue

    return plugin_rules


def get_rules() -> dict[str, list[Rule]]:
    """
    Get combined rules from built-in rules and loaded plugins.

    Plugin rules take priority and can override built-in rules.
    """
    rules = {}

    # Start with built-in rules
    for ecosystem, builtin_rules in BUILTIN_RULES.items():
        rules[ecosystem] = list(builtin_rules)

    # Add/override with plugin rules
    plugin_rules = _load_plugin_rules()
    for ecosystem, additional_rules in plugin_rules.items():
        if ecosystem not in rules:
            rules[ecosystem] = []
        # Plugin rules are added, allowing for extension or override
        rules[ecosystem].extend(additional_rules)

    return rules
