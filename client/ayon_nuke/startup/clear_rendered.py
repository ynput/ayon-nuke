"""Old entry point of the `Clear Rendered` button.

Render groups store the button's command in the workfile; groups made
before the code moved to `ayon_nuke.api.utils` run
`import clear_rendered; clear_rendered.clear_rendered_from_node(...)`, and
older ones `clear_rendered.clear_rendered("<render folder>")`. This module
keeps both commands working.
"""
from ayon_nuke.api.utils import (  # noqa: F401
    clear_rendered,
    clear_rendered_from_node,
)
