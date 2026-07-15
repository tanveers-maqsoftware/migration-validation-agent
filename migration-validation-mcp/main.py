"""Entry point for the Migration Validation MCP server.

Launches the MCP server defined in ``migration_validation/server.py`` so the project can be
started with ``python main.py`` or via the ``migration-validation-mcp`` script
declared in ``pyproject.toml``.
"""

from migration_validation.server import run


def main():
    run()


if __name__ == "__main__":
    main()
