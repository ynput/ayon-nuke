from __future__ import annotations

import abc
import json
from collections.abc import Collection

import nuke

from ayon_core.lib import BoolDef
from ayon_nuke.api import parse_container, plugin
from ayon_nuke.api.lib import link_knobs

# Links of `Node.dependent` that are node inputs, not expression links.
_INPUT_LINKS = nuke.INPUTS | nuke.HIDDEN_INPUTS


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
            skip_classes: Collection[str] = frozenset()) -> str:
        """Create the nodes of an effect JSON inside the group node

        Args:
            json_f (dict): The effect JSON data.
            group_node (nuke.Node): The group node to load the nodes into.
            skip_classes (Collection[str]): Node classes not to create.

        """

        # get correct order of nodes by positions on track and subtrack
        nodes_order = self._reorder_nodes(json_f)

        # Nuke 17 disconnects the group's inputs when their Input nodes are
        # deleted below (Nuke 16 keeps them): remember them to restore.
        inputs = [group_node.input(i) for i in range(group_node.inputs())]

        # adding content to the group node
        nuke.endGroup()  # jump out of group if we happen to be in one
        with group_node:
            # first remove all nodes if any in the group
            for node in group_node.nodes():
                nuke.delete(node)
            self._create_nodes_order(nodes_order, skip_classes)

        for index, node in enumerate(inputs):
            if node is not None and group_node.input(index) is None:
                group_node.setInput(index, node)

        return json_f["assignTo"]

    def _create_nodes_order(
            self,
            nodes_order: dict,
            skip_classes: Collection[str] = frozenset()):
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

    def _without_classes(
            self, nodes_order: dict, skip_classes: Collection[str]) -> dict:
        """Return the ordered nodes without the given node classes.

        Logs which nodes are dropped, so a skipped node stays traceable.
        """
        kept = {}
        for key, node_data in nodes_order.items():
            if node_data["class"] not in skip_classes:
                kept[key] = node_data
                continue

            node_name = (node_data.get("node") or {}).get("name")
            self.log.info(
                "Skipping effect node '%s' (%s): its class is in the "
                "skipped node classes.",
                node_name or key,
                node_data["class"],
            )

        if nodes_order and not kept:
            self.log.warning(
                "All nodes of the effect are skipped, its group only "
                "passes the input through."
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

    # Loaded from settings
    exposed_knobs: list[str] = []
    """Names of knobs to expose on the group node."""

    skip_node_classes: list[str] = []
    """Node classes not to create on a Read node loaded with retime."""

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
        # Imprinted on the container, so an update attaches the same way.
        self._attach_to_read_node = attach_to_read_node

        json_f = self._load_effect_json(context)

        read_node = None
        if attach_to_read_node:
            read_node = self._find_read_node(namespace, json_f["assignTo"])

        # A loaded plate already re-creates its retime on the read node.
        # The effect JSON contains that same retime, creating it here as
        # well would apply it twice. Opt-in: the setting lists the classes.
        skip_classes = frozenset()
        skipped_retime = False
        # Each lookup scans the whole script, so it runs once per load.
        retime_nodes = []
        if read_node is not None and self.skip_node_classes:
            retime_nodes = self._get_retime_nodes(read_node)
        if retime_nodes:
            skip_classes = frozenset(self.skip_node_classes)
            # Only an effect that had the Read's retime on top of it was
            # above the TimeWarp in the editor, so only that one belongs
            # after the Read's retime nodes.
            retime_classes = {node.Class() for node in retime_nodes}
            nodes_order = self._reorder_nodes(json_f)
            retime_keys = [
                key
                for key, entry in nodes_order.items()
                if entry["class"] in skip_classes
                and entry["class"] in retime_classes
            ]
            skipped_retime = bool(retime_keys)
            if skipped_retime:
                self._warn_nodes_below_retime(
                    nodes_order, skip_classes, retime_keys[0])

        self._load_effects_to_group(json_f, group_node, skip_classes)
        self._expose_knobs(group_node)
        if read_node is not None:
            if skipped_retime:
                self._connect_after_retime(group_node, retime_nodes)
            else:
                self._connect_read_node(group_node, read_node)

    def on_update(self, group_node, namespace, context):
        # Do the exact same as on load, attached as the load chose. The
        # option decides which nodes are skipped, so an update must not
        # fall back to the setting. Containers loaded before the choice
        # was imprinted have no knob and keep using the setting.
        options = {}
        container = parse_container(group_node) or {}
        attach_to_read_node = container.get("attachToReadNode")
        if attach_to_read_node is not None:
            # Imprinted data is read back as a string.
            options["attach_to_read_node"] = (
                str(attach_to_read_node) == "True"
            )
        self.on_load(group_node, namespace, context, options)
        return group_node

    def _get_imprint_data(self, context: dict) -> dict:
        data = super()._get_imprint_data(context)
        attach_to_read_node = getattr(self, "_attach_to_read_node", None)
        if attach_to_read_node is not None:
            # A string, so it reads back the same from any knob type.
            data["attachToReadNode"] = str(bool(attach_to_read_node))
        return data

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

    def _get_retime_nodes(self, read_node) -> list:
        """Return the retime nodes `LoadClip` made for the read node.

        `LoadClip` marks its retime nodes with the read node's container id.
        Unlike the imprinted `addRetime`, this also sees a plate updated to
        a version without retime, or a retime deleted by hand.
        """
        id_knob_name = plugin.NukeLoader.container_id_knob
        id_knob = read_node.knob(id_knob_name)
        container_id = id_knob.value() if id_knob else None
        if not container_id:
            return []

        read_name = read_node.fullName()
        return [
            node
            for node in nuke.allNodes(recurseGroups=True)
            if (
                node.fullName() != read_name
                and node.knob(id_knob_name) is not None
                and node.knob(id_knob_name).value() == container_id
                # A copy of the read node is a container of its own.
                and not parse_container(node)
            )
        ]

    def _last_retime_node(self, retime_nodes: list):
        """Return the retime node the effect group belongs after."""
        retime_names = {node.fullName() for node in retime_nodes}
        for node in retime_nodes:
            if not any(
                dependent.fullName() in retime_names
                for dependent in node.dependent(_INPUT_LINKS)
            ):
                return node
        return retime_nodes[-1]

    def _warn_nodes_below_retime(
            self,
            nodes_order: dict,
            skip_classes: Collection[str],
            retime_key: str) -> None:
        """Warn about the effect nodes that were below the skipped retime.

        The group goes after the Read's retime as a whole, so the nodes
        that came before the retime in the effect now run after it too,
        and their animated knobs are read on other frames than in the
        editor.
        """
        below = []
        for key, entry in nodes_order.items():
            if key == retime_key:
                break
            if entry["class"] not in skip_classes:
                below.append((entry.get("node") or {}).get("name") or key)

        if below:
            self.log.warning(
                "Effect nodes %s were below '%s' in the editor, they now "
                "run after the Read's retime: their animation may be "
                "shifted by the retime.",
                ", ".join(below),
                retime_key,
            )

    def _connect_after_retime(self, group_node, retime_nodes: list):
        """Connect the group after the read node's retime nodes.

        The effect was above the TimeWarp in the editor, so it has to run
        after the retime to keep the animated knobs on timeline frames.
        """
        # Out of its place first, so it does not hide the last retime node.
        self._detach(group_node)
        self._insert_below(group_node, self._last_retime_node(retime_nodes))

    def _detach(self, group_node):
        """Take the group out of the chain it is in, keeping the chain whole.

        An update may move the group, when the setting or the Read's retime
        changed since the load: what read the group reads its input now.
        A group without an input keeps what reads it.
        """
        upstream = group_node.input(0)
        if upstream is None:
            return
        self._rewire_inputs(group_node, upstream)
        group_node.setInput(0, None)

    def _insert_below(self, group_node, node):
        """Insert the group below `node`, in front of what read `node`."""
        self._rewire_inputs(node, group_node)
        group_node.setInput(0, node)
        group_node.autoplace()

    @staticmethod
    def _rewire_inputs(source, target):
        """Point the inputs that read `source` at `target` instead.

        Only input connections count, not expression links, and only the
        inputs that read `source` change: a Merge that reads it on A keeps
        its B.
        """
        source_name = source.fullName()
        for dependent in source.dependent(_INPUT_LINKS):
            for index in range(dependent.inputs()):
                upstream = dependent.input(index)
                if (
                    upstream is not None
                    and upstream.fullName() == source_name
                ):
                    dependent.setInput(index, target)

    def _find_read_node(self, namespace, product_name):
        """Find the read node loaded for the effect's product.

        Loaded clips are matched on the container data (`namespace` and
        `name`), so a renamed node or a custom file path still finds the
        right Read. Reads without container data fall back to the old
        `"<namespace>_<product>"` path match.

        Several loads of the same product cannot be told apart: the first
        by node name is used and a warning lists the candidates.

        Arguments:
            namespace (str): namespace name to search read node for.
            product_name (str): product name to search read node for.

        Returns:
            nuke.Node: the read node, or None when nothing was found.
        """
        matches = []
        for node in nuke.allNodes(filter="Read"):
            container = parse_container(node) or {}
            if (
                container.get("namespace") == namespace
                and container.get("name") == product_name
            ):
                matches.append(node)

        if matches:
            matches.sort(key=lambda node: node.fullName())
            if len(matches) > 1:
                self.log.warning(
                    "Several Read nodes were loaded for '%s_%s': %s. "
                    "Using '%s'.",
                    namespace,
                    product_name,
                    ", ".join(node.fullName() for node in matches),
                    matches[0].fullName(),
                )
            return matches[0]

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

        self._detach(group_node)
        self._insert_below(group_node, read_node)


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
