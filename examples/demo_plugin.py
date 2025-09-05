"""Demo plugin for AutoRepro with sleep and envcheck rules."""

from autorepro.rules import Rule


def provide_rules():
    """Provide plugin rules for testing."""
    return {
        "python": [
            Rule(
                'python -c "import time, sys; time.sleep(3); sys.exit(0)"',
                {"sleep"},
                10,
                {"demo"},
            ),
            Rule("pytest -q -k envcheck", {"envcheck"}, 10, {"test"}),
            Rule("pytest -q -k smoke", {"smoke"}, 10, {"test"}),
        ]
    }
