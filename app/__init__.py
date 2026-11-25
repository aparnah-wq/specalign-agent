"""SpecAlign ADK agent package."""

try:
    from . import agent
except ImportError:
    # Allows pure-Python tool modules (e.g. app.tools.doc_tools) to be imported
    # and unit-tested in minimal environments where google-adk is not installed.
    agent = None  # type: ignore[assignment]

__all__ = ["agent"]
