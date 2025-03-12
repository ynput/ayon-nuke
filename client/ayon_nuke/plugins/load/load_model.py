import nuke
import ayon_api

from ayon_core.pipeline import (
    load,
    get_representation_path,
)
from ayon_nuke.api.lib import maintained_selection
from ayon_nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop
)


class AlembicModelLoader(load.LoaderPlugin):
    """
    This will load alembic model or anim into script.

    Note: The class name `AlembicModelLoader` can't be changed for backward
        compatibility, even though it can read more than just alembic files.
    """

    product_types = {"model", "pointcache", "animation", "fbx", "usd"}
    representations = {"*"}
    extensions = {"abc", "fbx", "obj", "usd", "usda"}

    settings_category = "nuke"

    label = "Load Geo"
    icon = "cube"
    color = "orange"
    node_color = "0x4ecd91ff"

    def load(self, context, name, namespace, data):
        # get main variables
        project_name = context["project"]["name"]
        version_entity = context["version"]

        version_attributes = version_entity["attrib"]
        first = version_attributes.get("frameStart")
        last = version_attributes.get("frameEnd")
        fps = version_attributes.get("fps") or nuke.root()["fps"].getValue()

        namespace = namespace or context["folder"]["name"]
        object_name = "{}_{}".format(name, namespace)

        # prepare data for imprinting
        data_imprint = {
            "frameStart": first,
            "frameEnd": last,
            "version": version_entity["version"]
        }
        # add attributes from the version to imprint to metadata knob
        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes[k]

        # getting file path
        file = self.filepath_from_context(context).replace("\\", "/")

        with maintained_selection():
            model_node = nuke.createNode(
                "ReadGeo2",
                "name {} file {} ".format(
                    object_name, file),
                inpanel=False
            )
            model_node.forceValidate()

            # Force refresh
            self._select_all_items(model_node)
            model_node = self._fix_scene_view_contents(model_node)
            self._set_fps(model_node, fps)

        # color node by correct color by actual version
        self.node_version_color(project_name, version_entity, model_node)

        return containerise(
            node=model_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
            data=data_imprint)

    def update(self, container, context):
        """
            Called by Scene Inventory when look should be updated to current
            version.
            If any reference edits cannot be applied, eg. shader renamed and
            material not present, reference is unloaded and cleaned.
            All failed edits are highlighted to the user via message box.

        Args:
            container: object that has look to be updated
            context: (dict): relationship data to get proper
                                    representation from DB and persisted
                                    data in .json
        Returns:
            None
        """
        # Get version from io
        project_name = context["project"]["name"]
        version_entity = context["version"]
        repre_entity = context["representation"]

        # get corresponding node
        model_node = container["node"]

        # get main variables
        version_attributes = version_entity["attrib"]
        first = version_attributes.get("frameStart")
        last = version_attributes.get("frameEnd")
        fps = version_attributes.get("fps") or nuke.root()["fps"].getValue()

        # prepare data for imprinting
        data_imprint = {
            "representation": repre_entity["id"],
            "frameStart": first,
            "frameEnd": last,
            "version": version_entity["version"]
        }

        # add additional metadata from the version to imprint to Avalon knob
        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes[k]

        # getting file path
        file = get_representation_path(repre_entity).replace("\\", "/")

        model_node["file"].setValue(file)
        self._select_all_items(model_node)
        with maintained_selection():
            model_node = self._fix_scene_view_contents(model_node)
        self._set_fps(model_node, fps)

        # color node by correct color by actual version
        self.node_version_color(project_name, version_entity, model_node)

        self.log.info(
            "updated to version: {}".format(version_entity["version"])
        )

        return update_container(model_node, data_imprint)

    def _select_all_items(self, node):
        # Alembic
        scene_view = node.knob("scene_view")
        if scene_view is not None:
            # Ensure all items are imported and selected.
            scene_view.setImportedItems(scene_view.getAllItems())
            scene_view.setSelectedItems(scene_view.getAllItems())
            return

        # USD
        scene_graph = node.knob("scene_graph")
        if scene_graph is not None:
            items = scene_graph.getItems()
            names = [x[0] for x in items]
            scene_graph.setSelectedItems(names)
            return

    def _fix_scene_view_contents(self, node: nuke.Node) -> nuke.Node:
        """Fix UI not displaying `scene_view` or `scene_graph` correctly."""
        node['selected'].setValue(True)

        # collect input output dependencies
        dependencies = node.dependencies()
        dependent = node.dependent()

        # workaround because nuke's bug is
        # not adding animation keys properly
        xpos = node.xpos()
        ypos = node.ypos()
        nuke.nodeCopy("%clipboard%")
        nuke.delete(node)

        # paste the node back and set the position
        nuke.nodePaste("%clipboard%")
        node = nuke.selectedNode()
        node.setXYpos(xpos, ypos)

        # link to original input nodes
        for i, input in enumerate(dependencies):
            node.setInput(i, input)

        # link to original output nodes
        for d in dependent:
            index = next(
                (
                    i
                    for i, dpcy in enumerate(d.dependencies())
                    if node is dpcy
                ),
                0,
            )
            d.setInput(index, node)

        return node

    def _set_fps(self, node, fps):
        # Loaded USD files don't expose frame rate knob so it may not exist
        # so we only set `frame_rate` if it's exposed, e.g. on loaded Alembic
        knob = node.knob("frame_rate")
        if knob is None:
            return
        knob.setValue(float(fps))

    def node_version_color(self, project_name, version_entity, node):
        """ Coloring a node by correct color by actual version"""

        last_version_entity = ayon_api.get_last_version_by_product_id(
            project_name, version_entity["productId"], fields={"id"}
        )

        # change color of node
        if version_entity["id"] == last_version_entity["id"]:
            color_value = self.node_color
        else:
            color_value = "0xd88467ff"
        node["tile_color"].setValue(int(color_value, 16))

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = nuke.toNode(container['objectName'])
        with viewer_update_and_undo_stop():
            nuke.delete(node)
