import nuke
from ayon_nuke.api import (
    containerise,
    plugin,
    update_container,
)
from ayon_nuke.api.command import undo_chunk
from ayon_nuke.api.lib import color_to_int, maintained_selection


class GeoImportLoader(plugin.NukeLoader):
    """This will load files to GeoImport node."""

    product_base_types = {"*"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {"abc", "usd", "usda", "usdc"}
    order = 2

    settings_category = "nuke"

    label = "Load GeoImport"
    icon = "cube"
    color = "orange"

    node_color_latest   = color_to_int(78, 205, 145)   # 0x4ecd91ff
    node_color_outdated = color_to_int(216, 132, 103)  # 0xd88467ff

    node_class = "GeoImport"
    node_file_knob = "file"

    @undo_chunk("Load GeoImport")
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

        container = containerise(
            node=node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
        )
        self.update_node_color(node)  # after containerise
        return container

    @undo_chunk("Update GeoImport")
    def update(self, container, context):
        node: nuke.Node = container["node"]
        file = self.filepath_from_context(context).replace("\\", "/")
        node[self.node_file_knob].setValue(file)

        # update representation id
        container = update_container(
            node,
            {
                "representation": context["representation"]["id"],
            },
        )
        self.update_node_color(node)  # after update_container
        return container

    def switch(self, container, context):
        self.update(container, context)

    @undo_chunk("Remove GeoImport")
    def remove(self, container):
        node = nuke.toNode(container["objectName"])
        nuke.delete(node)


class GeoReferenceLoader(GeoImportLoader):
    """This will load files to GeoReference node."""
    label = "Load GeoReference"
    order = 3

    node_class = "GeoReference"
    node_file_knob = "file_path"
