import pyblish.api

from ayon_nuke import api as napi
from ayon_core.pipeline.publish import RepairAction
from ayon_core.pipeline import (
    PublishXmlValidationError,
    OptionalPyblishPluginMixin
)

import nuke


class ValidateOutputResolution(
    OptionalPyblishPluginMixin,
    pyblish.api.InstancePlugin
):
    """Validates Output Resolution.

    It is making sure the resolution of write's input is the same as
    Format definition of script in Root node.
    """

    order = pyblish.api.ValidatorOrder
    optional = True
    families = ["render"]
    label = "Validate Write resolution"
    hosts = ["nuke"]
    actions = [RepairAction]

    settings_category = "nuke"

    missing_msg = "Missing Reformat node in render group node"
    resolution_msg = "Reformat is set to wrong format"

    def process(self, instance):
        if not self.is_active(instance.data):
            return

        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishXmlValidationError(self, invalid)

    @classmethod
    def get_reformat(cls, node: nuke.Node) -> nuke.Node | None:
        """Find a reformat node under the given node."""

        # if it is not a group node,
        # we check if the node has a "format" knob and assume it
        # can be used to control the output format
        if not isinstance(node, nuke.Group):
            if "format" in node.knobs():
                return node
            return None

        # if it is a group node, we look for a child reformat node
        reformat_nodes = [n for n in node.nodes() if n.Class() == "Reformat"]
        if reformat_nodes:
            # todo: decide what to do if there are multiple reformat nodes
            return reformat_nodes[0]

        # add a new reformat node under the group node
        # TODO: test this
        with napi.maintained_selection():
            node['selected'].setValue(True)
            reformat_node = nuke.createNode("Reformat", "name Reformat01")
            reformat_node["resize"].setValue(0)
            reformat_node["black_outside"].setValue(1)
            return reformat_node

    @classmethod
    def get_invalid(cls, instance) -> str | None:
        root_width = instance.data["resolutionWidth"]
        root_height = instance.data["resolutionHeight"]

        node: nuke.Node = instance.data["transientData"]["node"]
        node_format = node.format()  # can be accessed without cooking the node
        node_width = node_format.width()
        node_height = node_format.height()

        correct_format = (root_width == node_width) and (root_height == node_height)
        if not correct_format:
            return cls.resolution_msg
        return None

    @classmethod
    def repair(cls, instance: pyblish.api.Instance) -> None:
        invalid_msg = cls.get_invalid(instance)
        if not invalid_msg:
            return

        node: nuke.Node = instance.data["transientData"]["node"]
        reformat_node = cls.get_reformat(node)
        if reformat_node:
            reformat_node["format"].setValue(nuke.root()["format"].value())
            cls.log.info("Fixing reformat to root.format")
        else:
            cls.log.error("No reformat node found")
