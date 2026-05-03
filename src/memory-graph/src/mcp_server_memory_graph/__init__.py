from .config import Settings
from .server import build_server, run


def main() -> None:
    """Entrypoint for the `mcp-server-memory-graph` console script."""
    import logging

    logging.basicConfig(level=logging.INFO)
    run(Settings())


__all__ = ["build_server", "main", "run", "Settings"]
