from __future__ import annotations

import os
import typing

from ayon_core.lib import Logger


if typing.TYPE_CHECKING:
    import nuke


log = Logger.get_logger(__name__)


def clear_rendered(dir_path):
    """Delete rendered files for the given directory."""
    for _f in os.listdir(dir_path):
        _f_path = os.path.join(dir_path, _f)
        log.info("Removing: `{}`".format(_f_path))
        os.remove(_f_path)


def _clear_rendered_for_write_node(node: nuke.Node) -> None:
    """Delete rendered files for the given write node."""
    path = node["file"].evaluate()
    dir_path = os.path.dirname(path)
    clear_rendered(dir_path)


def clear_rendered_from_node(node: nuke.Node) -> None:
    """Delete rendered files for the given node and all its children."""
    node_class = node.Class()
    if node_class == "Write":
        _clear_rendered_for_write_node(node)
        return

    if node_class == "Group":
        for child in node.nodes():
            clear_rendered_from_node(child)
        return
    
    log.error(f"Unsupported node class: `{node_class}`")
