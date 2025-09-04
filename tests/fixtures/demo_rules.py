"""Demo plugin rules for testing."""

from autorepro.rules import Rule


def provide_rules():
    """Provide additional rules for testing plugin system."""
    return {
        "python": [
            Rule(
                "pytest -q -k smoke",
                {"pytest", "smoke"},
                weight=1,
                tags={"test", "plugin"},
            ),
        ]
    }
