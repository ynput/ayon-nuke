from __future__ import annotations

import abc
import json

import nuke

from ayon_core.lib import BoolDef
from ayon_nuke.api import parse_container, plugin
from ayon_nuke.api.lib import link_knobs


class _BaseEffectsLoader(
    abc.ABC,
    plugin.NukeGroupLoader,
):
    """Base class for loading effects"""

    product_base_types = {"effect"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {"json"}

    label = "Load Effects"
    order = 0
    icon = "cc"
    color = "white"

    @abc.abstractmethod
    def on_load(self, group_node, namespace, context, options=None):
        pass

    def _load_effect_json(self, context: dict) -> dict:
        """Read the effect JSON file for the given context."""
        file = self.filepath_from_context(context).replace("\\", "/")
        with open(file, "r") as f:
            return json.load(f)

    def _load_effects_to_group(
            self,
            json_f: dict,
            group_node: nuke.Node,
            skip_classes: set[str] = frozenset()) -> str:
        """Create the nodes of an effect JSON inside the group node

        Args:
            json_f (dict): The effect JSON data.
            group_node (nuke.Node): The group node to load the nodes into.
            skip_classes (set[str]): Node classes not to create.

        """

        # get correct order of nodes by positions on track and subtrack
        nodes_order = self._reorder_nodes(json_f)

        # adding content to the group node
        nuke.endGroup()  # jump out of group if we happen to be in one
        with group_node:
            # first remove all nodes if any in the group
            for node in group_node.nodes():
                nuke.delete(node)
            self._create_nodes_order(nodes_order, skip_classes)

        return json_f["assignTo"]

    def _create_nodes_order(
            self, nodes_order: dict, skip_classes: set[str] = frozenset()):
        workfile_first_frame = int(nuke.root()["first_frame"].getValue())

        if skip_classes:
            nodes_order = self._without_classes(nodes_order, skip_classes)

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

    def _without_classes(self, nodes_order: dict, skip_classes: set[str]):
        """Return the ordered nodes without the given node classes.

        Logs which nodes are dropped, so skipping a retime stays traceable.
        """
        kept = {}
        for key, node_data in nodes_order.items():
            if node_data["class"] not in skip_classes:
                kept[key] = node_data
                continue

            node_name = (node_data.get("node") or {}).get("name")
            self.log.info(
                "Skipping retime node '%s' ('%s'): the clip it is "
                "attached to already has a retime.",
                node_name or node_data["class"],
                node_data["class"],
            )

        return kept

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


class LoadEffects(_BaseEffectsLoader):
    """Loading colorspace soft effect exported from nukestudio"""

    label = "Load Effects - nodes"
    order = 0
    icon = "cc"
    color = "white"

    attach_to_read_node = True

    retime_node_classes = frozenset({"TimeWarp", "Retime"})
    """Node classes of a retime the loaded clip already carries."""

    # Loaded from settings
    exposed_knobs: list[str] = []
    """Names of knobs to expose on the group node."""

    @classmethod
    def get_options(cls, *args):
        return [
            BoolDef(
                "attach_to_read_node",
                label="Attach to Read Node",
                default=cls.attach_to_read_node,
            ),
        ]

    def on_load(self, group_node, namespace, context, options=None):
        options = options or {}
        # Without the option (update, scripts, workfile builder) the
        # setting decides: loads always attached to the Read node before.
        attach_to_read_node = options.get(
            "attach_to_read_node", self.attach_to_read_node
        )

        json_f = self._load_effect_json(context)

        read_node = None
        if attach_to_read_node:
            read_node = self._find_read_node(namespace, json_f["assignTo"])

        # A loaded plate already re-creates its retime on the read node.
        # The effect JSON contains that same retime, creating it here as
        # well would apply it twice.
        skip_classes = frozenset()
        if read_node is not None:
            container = parse_container(read_node) or {}
            if container.get("addRetime"):
                skip_classes = self.retime_node_classes

        self._load_effects_to_group(json_f, group_node, skip_classes)
        self._expose_knobs(group_node)
        if read_node is not None:
            self._connect_read_node(group_node, read_node)

    def on_update(self, group_node, namespace, context):
        # Do the exact same os on load
        self.on_load(group_node, namespace, context)
        return group_node

    def _expose_knobs(self, group_node: nuke.Group) -> None:
        """Expose configured knobs from child nodes onto the group.

        On update the child nodes are rebuilt, so a link created by a
        previous load points at a deleted node. The link knob is kept and
        pointed at the new node (not removed and added again), so it stays
        at its place and in its tab of the group.
        """
        if not self.exposed_knobs:
            return

        children = [
            node
            for node in group_node.nodes()
            if node.Class() not in ("Input", "Output")
        ]

        group_knobs = group_node.knobs()

        for knob_name in self.exposed_knobs:
            existing = group_knobs.get(knob_name)
            if existing is not None and not isinstance(
                existing, nuke.Link_Knob
            ):
                # A real knob of the group, never replace or remove it.
                self.log.warning(
                    "Group already has a knob '%s', not exposing it.",
                    knob_name,
                )
                continue

            # TODO: handle multiple children with the same knob
            owner = next(
                (child for child in children if child.knob(knob_name)),
                None,
            )
            if owner is None:
                self.log.warning("No child contains a knob '%s'", knob_name)
                if existing is not None:
                    # Stale link from a previous load or update.
                    group_node.removeKnob(existing)
                continue

            if existing is None:
                link_knobs([knob_name], owner, group_node)
            else:
                existing.makeLink(owner.name(), knob_name)

    def _find_read_node(self, namespace, product_name):
        """Find the read node loaded for the effect's product.

        Arguments:
            namespace (str): namespace name to search read node for.
            product_name (str): product name to search read node for.

        Returns:
            nuke.Node: the read node, or None when nothing was found.
        """
        search_name = "{0}_{1}".format(namespace, product_name)

        return next(
            (
                n for n in nuke.allNodes(filter="Read")
                if search_name in n["file"].value()
            ),
            None
        )

    def connect_read_node(self, group_node, namespace, product_name):
        """Find the read node and connect the group under it.

        Arguments:
            group_node (nuke.Node): Group node to connect to.
            namespace (str): namespace name to search read node for.
            product_name (str): product name to search read node for.

        """
        read_node = self._find_read_node(namespace, product_name)
        self._connect_read_node(group_node, read_node)

    def _connect_read_node(self, group_node, read_node):
        """Connect the group under the read node, keeping its dependents."""
        if not read_node:
            return

        dep_nodes = read_node.dependent()

        if len(dep_nodes) > 0:
            for dn in dep_nodes:
                dn.setInput(0, group_node)

        group_node.setInput(0, read_node)
        group_node.autoplace()


class LoadEffectsInputProcess(_BaseEffectsLoader):
    """Loading colorspace soft effect exported from nukestudio"""

    label = "Load Effects - Input Process"
    icon = "eye"
    color = "#cc0000"

    def on_load(self, group_node, namespace, context, options=None):
        # try to place it under Viewer1
        json_f = self._load_effect_json(context)
        self._load_effects_to_group(json_f, group_node=group_node)
        if not self.connect_active_viewer(group_node):
            nuke.delete(group_node)
            return

    def on_update(self, group_node, namespace, context):
        # No post-process on update
        # Only overridden to avoid behavior of LoadEffects
        return group_node
