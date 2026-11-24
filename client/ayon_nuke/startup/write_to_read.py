"""Old entry point of the `Read From Rendered` button.

Render groups store the button's command in the workfile; groups made
before the code moved to `ayon_nuke.api.utils` run
`import write_to_read; write_to_read.write_to_read(nuke.thisNode(), ...)`.
This module keeps that command working.
"""
from ayon_nuke.api.utils import read_from_rendered


def write_to_read(gn, allow_relative=False):
    """Create a Read node for the render of group `gn`.

    `allow_relative` is ignored: the button always passed False.
    """
    return read_from_rendered(gn)
