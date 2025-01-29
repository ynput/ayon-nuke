import json

import nuke

import ayon_api
from ayon_core.pipeline import load
from ayon_nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop
)
from ayon_nuke.api import lib


class LoadEffects(load.LoaderPlugin):
    """Loading colorspace soft effect exported from nukestudio"""

    product_types = {"effect"}
    representations = {"*"}
    extensions = {"json"}

    settings_category = "nuke"

    label = "Load Effects - nodes"
    order = 0
    icon = "cc"
    color = "white"
    ignore_attr = ["useLifetime"]

    def load(self, context, name, namespace, data):
        """
        Loading function to get the soft effects to particular read node

        Arguments:
            context (dict): context of version
            name (str): name of the version
            namespace (str): namespace name
            data (dict): compulsory attribute > not used

        Returns:
            nuke.Node: containerised nuke node object
        """
        object_name = "{}_{}".format(name, namespace)

        group_node: nuke.Group = nuke.createNode(
            "Group",
            "name {}_1".format(object_name),
            inpanel=False
        )

        # load effects json and create nodes inside the group
        json_f = self._load_effects_data(context)
        self._load_nodes_to_group(json_f, group_node=group_node)
        self.on_load(group_node, namespace, json_f["assignTo"])

        # On load may have deleted the group node. If it did, then we stop here
        if not group_node:
            return

        self._set_node_color(group_node, context)

        self.log.info(
            "Loaded lut setup: `{}`".format(group_node["name"].value()))

        data_imprint = self._get_imprint_data(context, name, namespace)
        return containerise(
            node=group_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
            data=data_imprint)

    def update(self, container, context):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """
        group_node: nuke.Group = container["node"]
        namespace: str = container["namespace"]

        # load effects json and create nodes inside the group
        json_f = self._load_effects_data(context)
        self._load_nodes_to_group(json_f, group_node=group_node)

        # Trigger load logic on the created group
        self.on_update(group_node, namespace, json_f)

        # change color of node
        self._set_node_color(group_node, context)

        # Update the imprinted representation
        data_imprint = self._get_imprint_data(context)
        update_container(
            group_node,
            data_imprint
        )

        self.log.info(
            "updated to version: {}".format(context["version"]["version"])
        )

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = container["node"]
        with viewer_update_and_undo_stop():
            nuke.delete(node)

    # On load and on update are overridden by LoadEffectsInputProcess
    # for alternative behavior
    def on_load(self, group_node, namespace, json_f):
        self.connect_read_node(group_node, namespace, json_f["assignTo"])

    def on_update(self, group_node, namespace, json_f):
        self.connect_read_node(group_node, namespace, json_f["assignTo"])

    def connect_read_node(self, group_node, namespace, product_name):
        """
        Finds read node and selects it

        Arguments:
            group_node (nuke.Node): Group node to connect to.
            namespace (str): namespace name to search read node for.
            product_name (str): product name to search read node for.

        Returns:
            nuke node: node is selected
            None: if nothing found
        """
        search_name = "{0}_{1}".format(namespace, product_name)

        read_node = next(
            (
                n for n in nuke.allNodes(filter="Read")
                if search_name in n["file"].value()
            ),
            None
        )

        # Parent read node has been found
        # solving connections
        if read_node:
            dep_nodes = read_node.dependent()

            if len(dep_nodes) > 0:
                for dn in dep_nodes:
                    dn.setInput(0, group_node)

            group_node.setInput(0, read_node)
            group_node.autoplace()

    def _load_effects_data(self, context: dict) -> dict:
        file = self.filepath_from_context(context).replace("\\", "/")
        with open(file, "r") as f:
            return json.load(f)

    def _load_nodes_to_group(
            self, json_f: dict, group_node: nuke.Group):
        """Load the json file and create nodes inside the group node"""
        # get correct order of nodes by positions on track and subtrack
        nodes_order = self._reorder_nodes(json_f)

        # adding content to the group node
        nuke.endGroup()  # jump out of group if we happen to be in one
        with group_node:
            # first remove all nodes if any in the group
            for node in group_node.nodes():
                nuke.delete(node)
            self._create_nodes_order(nodes_order)

    def _create_nodes_order(self, nodes_order: dict):
        workfile_first_frame = int(nuke.root()["first_frame"].getValue())

        # create input node
        pre_node = nuke.createNode("Input")
        pre_node["name"].setValue("rgb")

        for ef_val in nodes_order.values():
            node = nuke.createNode(ef_val["class"])
            for k, v in ef_val["node"].items():
                if k in self.ignore_attr:
                    continue

                # Check if attribute is available
                try:
                    node[k].value()
                except NameError as e:
                    self.log.warning(e)
                    continue

                # Set node attribute values
                if isinstance(v, list) and len(v) > 4:
                    node[k].setAnimated()
                    for i, value in enumerate(v):
                        if isinstance(value, list):
                            for ci, cv in enumerate(value):
                                node[k].setValueAt(
                                    cv,
                                    (workfile_first_frame + i),
                                    ci)
                        else:
                            node[k].setValueAt(
                                value,
                                (workfile_first_frame + i))
                else:
                    node[k].setValue(v)
            node.setInput(0, pre_node)
            pre_node = node

        # create output node
        output = nuke.createNode("Output")
        output.setInput(0, pre_node)

        return pre_node

    def _get_imprint_data(self, context: dict) -> dict:
        """Return data to be imprinted from version."""
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        data = {
            "version": version_entity["version"],
            "colorspaceInput": version_attributes.get("colorSpace"),
        }
        for k in [
            "frameStart",
            "frameEnd",
            "handleStart",
            "handleEnd",
            "source",
            "fps"
        ]:
            data[k] = version_attributes[k]

        return data

    def _set_node_color(self, node, context):
        """Set node color based on whether version is latest"""
        is_latest = ayon_api.version_is_latest(
            context["project"]["name"], context["version"]["id"]
        )
        color_value = "0x3469ffff" if is_latest else "0xd84f20ff"
        node["tile_color"].setValue(int(color_value, 16))

    def _reorder_nodes(self, data: dict) -> dict:
        track_nums = [
            v["trackIndex"] for v in data.values() if isinstance(v, dict)]
        sub_track_nums = [
            v["subTrackIndex"] for v in data.values() if isinstance(v, dict)]

        new_order = {}
        for track_index in range(min(track_nums), max(track_nums) + 1):
            for sub_track_index in range(
                    min(sub_track_nums), max(sub_track_nums) + 1):
                item = self._get_item(data, track_index, sub_track_index)
                if item:
                    new_order.update(item)
        return new_order

    def _get_item(
            self, data: dict, track_index: int, sub_track_index: int) -> dict:
        return {key: val for key, val in data.items()
                if isinstance(val, dict)
                if sub_track_index == val["subTrackIndex"]
                if track_index == val["trackIndex"]}


class LoadEffectsInputProcess(LoadEffects):
    """Loading colorspace soft effect exported from nukestudio"""

    label = "Load Effects - Input Process"
    icon = "eye"
    color = "#cc0000"

    def on_load(self, group_node, namespace, json_f):
        # try to place it under Viewer1
        if not self.connect_active_viewer(group_node):
            nuke.delete(group_node)
            return

    def on_update(self, group_node, namespace, json_f):
        # No post-process on update
        # Only overridden to avoid behavior of LoadEffects
        pass

    def connect_active_viewer(self, group_node):
        """
        Finds Active viewer and
        place the node under it, also adds
        name of group into Input Process of the viewer

        Arguments:
            group_node (nuke node): nuke group node object

        """
        group_node_name = group_node["name"].value()

        viewer = [n for n in nuke.allNodes() if "Viewer1" in n["name"].value()]
        if len(viewer) > 0:
            viewer = viewer[0]
        else:
            msg = str("Please create Viewer node before you "
                      "run this action again")
            self.log.error(msg)
            nuke.message(msg)
            return None

        # get coordinates of Viewer1
        xpos = viewer["xpos"].value()
        ypos = viewer["ypos"].value()

        ypos += 150

        viewer["ypos"].setValue(ypos)

        # set coordinates to group node
        group_node["xpos"].setValue(xpos)
        group_node["ypos"].setValue(ypos + 50)

        # add group node name to Viewer Input Process
        viewer["input_process_node"].setValue(group_node_name)

        # put backdrop under
        lib.create_backdrop(
            label="Input Process",
            layer=2,
            nodes=[viewer, group_node],
            color="0x7c7faaff")

        return True
