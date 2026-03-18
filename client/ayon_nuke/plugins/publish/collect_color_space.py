from __future__ import annotations

import logging
import re
import typing

import nuke
import pyblish.api
from ayon_core.pipeline import publish

from ayon_nuke import api as napi


class CollectColorSpace(
    pyblish.api.InstancePlugin, publish.ColormanagedPyblishPluginMixin
):
    """Collect color space info

    This plugin collect the following data:

    - colorspace

    """

    order = pyblish.api.CollectorOrder + 0.0022  # TODO: check the order
    label = "Collect Color Space"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    # list of possible knob names to check for colorspace
    knob_names = ["colorspace"]

    if typing.TYPE_CHECKING:
        log: logging.Logger

    def _get_nodes_to_check(self, instance: pyblish.api.Instance) -> list[nuke.Node]:
        """Get nodes to check for colorspace."""
        node = instance.data["transientData"]["node"] # the main parent node
        nodes_to_check: list[nuke.Node] = [node]

        # add main and secondary "write nodes"
        if write_node := instance.data["transientData"].get("writeNode"):
            nodes_to_check.append(write_node)
        if write_nodes := instance.data["transientData"].get("writeNodes"):
            nodes_to_check.extend(write_nodes)

        # add all children of the node
        if isinstance(node, nuke.Group):
            nodes_to_check.extend(node.nodes())

        return nodes_to_check

    def process(self, instance: pyblish.api.Instance) -> None:

        # check if colorspace is already set
        if "colorspace" in instance.data:
            self.log.info("Colorspace already set")
            return

        # get colorspace from nodes
        nodes_to_check = self._get_nodes_to_check(instance)
        node, knob = napi.find_node_with_knob(nodes_to_check, self.knob_names)
        if not node or not knob:
            # TODO: fallback to workfile or project settings?
            self.log.warning("No colorspace found")
            return
        
        colorspace = knob.value()
        self.log.info(f"Colorspace found: {colorspace}")

        # remove default part of the string
        if "default (" in colorspace:
            colorspace = re.sub(r"default.\(|\)", "", colorspace)

        instance.data["colorspace"] = colorspace
        instance.data["versionData"] = {"colorspace": colorspace} # TODO: do we need this?
