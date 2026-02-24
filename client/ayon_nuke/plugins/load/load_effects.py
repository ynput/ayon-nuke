import json

import nuke

from ayon_nuke.api import plugin


class LoadEffects(plugin.NukeGroupLoader):
    """Loading colorspace soft effect exported from nukestudio"""

    product_base_types = {"effect"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {"json"}

    label = "Load Effects - nodes"
    order = 0
    icon = "cc"
    color = "white"

    def on_load(self, group_node, namespace, context):
        assign_to = self._load_effects_to_group(context, group_node=group_node)
        self.connect_read_node(group_node, namespace, assign_to)

    def on_update(self, group_node, namespace, context):
        # Do the exact same os on load
        self.on_load(group_node, namespace, context)
        return group_node

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

    def _load_effects_to_group(
            self, context: dict, group_node: nuke.Node) -> str:
        """Load the json file and create nodes inside the group node"""

        file = self.filepath_from_context(context).replace("\\", "/")
        with open(file, "r") as f:
            json_f = json.load(f)

        # get correct order of nodes by positions on track and subtrack
        nodes_order = self._reorder_nodes(json_f)

        # adding content to the group node
        nuke.endGroup()  # jump out of group if we happen to be in one
        with group_node:
            # first remove all nodes if any in the group
            for node in group_node.nodes():
                nuke.delete(node)
            self._create_nodes_order(nodes_order)

        return json_f["assignTo"]

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

    def on_load(self, group_node, namespace, context):
        # try to place it under Viewer1
        self._load_effects_to_group(context, group_node=group_node)
        if not self.connect_active_viewer(group_node):
            nuke.delete(group_node)
            return

    def on_update(self, group_node, namespace, context):
        # No post-process on update
        # Only overridden to avoid behavior of LoadEffects
        return group_node