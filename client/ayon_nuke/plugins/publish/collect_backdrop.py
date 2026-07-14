from __future__ import annotations
import pyblish.api
from ayon_nuke.api import lib
import nuke


class CollectBackdrops(pyblish.api.InstancePlugin):
    """Collect Backdrop node instance and its content
    """

    order = pyblish.api.CollectorOrder + 0.22
    label = "Collect Backdrop"
    hosts = ["nuke"]
    families = ["nukenodes"]

    settings_category = "nuke"

    def process(self, instance):
        transient_data: dict = instance.data["transientData"]
        backdrop_node: nuke.BackdropNode = transient_data["node"]

        child_nodes: list[nuke.Node] = [
            node for node in lib.get_backdrop_nodes(backdrop_node)
            # exclude viewer
            if node.Class() != "Viewer"
        ]

        # get all connections from outside of backdrop
        connections_in, connections_out = lib.get_dependent_nodes(child_nodes)
        transient_data["childNodes"] = child_nodes
        transient_data["nodeConnectionsIn"] = connections_in
        transient_data["nodeConnectionsOut"] = connections_out

        # make label nicer
        instance.data["label"] = "{0} ({1} nodes)".format(
            backdrop_node.name(),
            len(child_nodes)
        )

        self.log.debug("Backdrop instance collected: `{}`".format(instance))
