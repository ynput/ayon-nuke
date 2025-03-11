import nuke
import ayon_api

from ayon_core.pipeline import load
from ayon_nuke.api.lib import maintained_selection
from ayon_nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop,
)


class GeoImportLoader(load.LoaderPlugin):
    """This will load files to GeoImport node."""

    product_types = {"*"}
    representations = {"*"}
    extensions = {"abc", "usd", "usda", "usdc"}

    settings_category = "nuke"

    label = "Load GeoImport"
    icon = "cube"
    color = "orange"
    node_color = "0x4ecd91ff"

    node_class = "GeoImport"
    node_file_knob = "file"

    def load(self, context, name, namespace, data):
        namespace = namespace or context["folder"]["name"]
        object_name = "{}_{}".format(name, namespace)

        filepath = self.filepath_from_context(context).replace("\\", "/")

        with maintained_selection():
            file_knob: str = self.node_file_knob
            node = nuke.createNode(
                self.node_class,
                f"name {object_name} {file_knob} {filepath}",
                inpanel=False,
            )
            node.forceValidate()

        # color node by correct color by actual version
        self.set_node_version_color(node, context)

        return containerise(
            node=node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
        )

    def update(self, container, context):
        node: nuke.Node = container["node"]
        file = self.filepath_from_context(context).replace("\\", "/")
        node[self.node_file_knob].setValue(file)

        # color node by correct color by actual version
        self.set_node_version_color(node, context)

        # update representation id
        return update_container(
            node,
            {
                "representation": context["representation"]["id"],
            },
        )

    def set_node_version_color(self, node: nuke.Node, context: dict):
        """Coloring a node by correct color by actual version"""
        is_latest_version = ayon_api.version_is_latest(
            context["project"]["name"], context["version"]["id"]
        )
        color_value = self.node_color if is_latest_version else "0xd88467ff"
        node["tile_color"].setValue(int(color_value, 16))

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = nuke.toNode(container["objectName"])
        with viewer_update_and_undo_stop():
            nuke.delete(node)


class GeoReferenceLoader(GeoImportLoader):
    """This will load files to GeoReference node."""
    label = "Load GeoReference"

    node_class = "GeoReference"
    node_file_knob = "file_path"
