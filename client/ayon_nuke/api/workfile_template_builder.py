import collections
from typing import Any
import nuke

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.workfile.workfile_template_builder import (
    TemplateProfileNotFound,
    TemplateLoadFailed,
    AbstractTemplateBuilder,
    PlaceholderPlugin,
    PlaceholderItem
)

from .lib import (
    get_backdrop_nodes,
    get_extreme_positions,
    imprint,
    node_tempfile,
    refresh_node,
    reset_selection,
    select_nodes,
    get_main_window,
    WorkfileSettings,
)

PLACEHOLDER_SET = "PLACEHOLDERS_SET"


LEGACY_PLACEHOLDER_KEYS = {
    "product_type",   # replaced by "product_base_type" in ayon-core 1.8.0
    "family",
}
"""Legacy placeholder keys that are deprecated but still supported for
backward compatibility.
"""

class NukeTemplateBuilder(AbstractTemplateBuilder):
    """Concrete implementation of AbstractTemplateBuilder for nuke"""

    def import_template(self, path):
        """Import template into current scene.
        Block if a template is already loaded.

        Args:
            path (str): A path to current template (usually given by
            get_template_preset implementation)

        Returns:
            bool: Whether the template was successfully imported or not
        """

        # TODO check if the template is already imported

        nuke.nodePaste(path)
        reset_selection()

        return True


class NukePlaceholderPlugin(PlaceholderPlugin):
    skip_discovery = True

    node_color = 4278190335

    item_class = PlaceholderItem

    def _collect_scene_placeholders(self):
        # Cache placeholder data to shared data
        placeholder_nodes = self.builder.get_shared_populate_data(
            "placeholder_nodes"
        )
        if placeholder_nodes is None:
            placeholder_nodes = {}
            all_groups = collections.deque()
            all_groups.append(nuke.thisGroup())
            while all_groups:
                group = all_groups.popleft()
                for node in group.nodes():
                    if isinstance(node, nuke.Group):
                        all_groups.append(node)

                    node_knobs = node.knobs()
                    if (
                        "is_placeholder" not in node_knobs
                        or not node.knob("is_placeholder").value()
                    ):
                        continue

                    if "empty" in node_knobs and node.knob("empty").value():
                        continue

                    placeholder_nodes[node.fullName()] = node

            self.builder.set_shared_populate_data(
                "placeholder_nodes", placeholder_nodes
            )
        return placeholder_nodes

    def create_placeholder(self, placeholder_data):
        placeholder_data["plugin_identifier"] = self.identifier

        placeholder = nuke.nodes.NoOp()
        placeholder.setName("PLACEHOLDER")
        placeholder.knob("tile_color").setValue(self.node_color)

        imprint(placeholder, placeholder_data)
        imprint(placeholder, {"is_placeholder": True})
        placeholder.knob("is_placeholder").setVisible(False)

    def update_placeholder(self, placeholder_item, placeholder_data):
        node = nuke.toNode(placeholder_item.scene_identifier)
        imprint(node, placeholder_data)

    def _parse_placeholder_node_data(self, node: nuke.Node):
        placeholder_data: dict[str, Any] = {}

        def _get_knob_value(knob):
            if isinstance(knob, (nuke.EvalString_Knob, nuke.String_Knob)):
                # Do not evaluate the contents; return the exact
                # text value we set
                return knob.getText()
            else:
                return knob.getValue()

        # collect current placeholder keys
        for key in self.get_placeholder_keys():
            if knob := node.knob(key):
                placeholder_data[key] = _get_knob_value(knob)
            else:
                placeholder_data[key] = None

        # collect legacy placeholder keys for backward compatibility
        for key in LEGACY_PLACEHOLDER_KEYS:

            if placeholder_data.get(key) is not None:
                continue

            if knob := node.knob(key):
                self.log.warning(
                    f"Legacy placeholder key '{key}' on '{node.fullName()}'"
                    " is deprecated and will be removed in the future."
                    "\nPlease recreate the placeholder to fix this."
                )
                placeholder_data[key] = _get_knob_value(knob)

        return placeholder_data

    def delete_placeholder(self, placeholder):
        """Remove placeholder if building was successful"""
        placeholder_node = nuke.toNode(placeholder.scene_identifier)
        nuke.delete(placeholder_node)

    def collect_placeholders(self):
        output = []
        scene_placeholders = self._collect_scene_placeholders()
        for node_name, node in scene_placeholders.items():
            plugin_identifier_knob = node.knob("plugin_identifier")
            if (
                plugin_identifier_knob is None
                or plugin_identifier_knob.getValue() != self.identifier
            ):
                continue

            placeholder_data = self._parse_placeholder_node_data(node)
            output.append(
                self.item_class(node_name, placeholder_data, self)
            )

        return output

    def _move_to_placeholder_group(self, placeholder, nodes):
        """
        opening the placeholder's group and copying nodes in it.

        Returns :
            nodes (list): the new list of pasted nodes
        """
        groups_name = placeholder.data["group_name"]
        reset_selection()
        select_nodes(nodes)
        if groups_name:
            with node_tempfile() as filepath:
                nuke.nodeCopy(filepath)
                for node in nuke.selectedNodes():
                    nuke.delete(node)
                group = nuke.toNode(groups_name)
                group.begin()
                nuke.nodePaste(filepath)
                nodes = nuke.selectedNodes()
        return nodes

    def _update_nodes(self, placeholder, nodes, considered_nodes):
        """Adjust backdrop nodes dimensions and positions.

        Considering some nodes sizes.

        Args:
            nodes (list): list of nodes to update
            considered_nodes (list): list of nodes to consider while updating
                positions and dimensions
        """

        placeholder_node = nuke.toNode(placeholder.scene_identifier)

        min_x, min_y, max_x, max_y = get_extreme_positions(considered_nodes)

        width_ph = placeholder_node.screenWidth()
        height_ph = placeholder_node.screenHeight()
        diff_y = max_y - min_y - height_ph
        diff_x = max_x - min_x - width_ph
        contained_nodes = {placeholder_node}  # for backdrops
        min_x = placeholder_node.xpos()
        min_y = placeholder_node.ypos()

        if diff_y <= 0 and diff_x <= 0:
            return

        for node in nodes:
            refresh_node(node)

            if (
                node == placeholder_node
                or node in considered_nodes
            ):
                continue

            if (
                not isinstance(node, nuke.BackdropNode)
                or (
                    isinstance(node, nuke.BackdropNode)
                    and not contained_nodes <= set(get_backdrop_nodes(node))
                )
            ):
                if node.xpos() >= min_x:
                    node.setXpos(node.xpos() + diff_x)

                if node.ypos() >= min_y:
                    node.setYpos(node.ypos() + diff_y)

            else:
                width = node.screenWidth()
                height = node.screenHeight()
                node.knob("bdwidth").setValue(width + diff_x)
                node.knob("bdheight").setValue(height + diff_y)

            refresh_node(node)


def trigger_on_app_launch() -> None:
    """Build the workfile template during application launch."""
    builder = NukeTemplateBuilder(registered_host())
    builder.trigger_on_app_launch()
    WorkfileSettings().set_context_settings()


def trigger_on_new_file() -> None:
    """Build the workfile template when a new file is created."""
    builder = NukeTemplateBuilder(registered_host())
    builder.trigger_on_new_file()
    WorkfileSettings().set_context_settings()


def build_workfile_template():
    builder = NukeTemplateBuilder(registered_host())
    preset = builder.get_template_preset()
    if not preset.profile:
        raise TemplateProfileNotFound(
            "No matching profile found for current context."
        )
    if not preset.has_valid_path():
        raise TemplateLoadFailed(f"Invalid template path: {preset.path}")
    builder.build_template(preset=preset)

    # set all settings to shot context default
    WorkfileSettings().set_context_settings()


def update_workfile_template(*args):
    builder = NukeTemplateBuilder(registered_host())
    builder.rebuild_template()


def open_template() -> None:
    """Open the workfile template UI for Nuke."""
    from ayon_core.tools.workfile_template_build import open_template_ui
    builder = NukeTemplateBuilder(registered_host())
    open_template_ui(builder, main_window=get_main_window())


def create_placeholder(*args):
    if not nuke.GUI:
        raise RuntimeError("Invalid in non-GUI mode.")

    from ayon_core.tools.workfile_template_build import (
        WorkfileBuildPlaceholderDialog,
    )

    host = registered_host()
    builder = NukeTemplateBuilder(host)
    window = WorkfileBuildPlaceholderDialog(host, builder,
                                            parent=get_main_window())
    window.show()


def update_placeholder(*args):
    if not nuke.GUI:
        raise RuntimeError("Invalid in non-GUI mode.")

    from ayon_core.tools.workfile_template_build import (
        WorkfileBuildPlaceholderDialog,
    )

    host = registered_host()
    builder = NukeTemplateBuilder(host)
    placeholder_items_by_id = {
        placeholder_item.scene_identifier: placeholder_item
        for placeholder_item in builder.get_placeholders()
    }
    placeholder_items = []
    for node in nuke.selectedNodes():
        node_name = node.fullName()
        if node_name in placeholder_items_by_id:
            placeholder_items.append(placeholder_items_by_id[node_name])

    # TODO show UI at least
    if len(placeholder_items) == 0:
        raise ValueError("No node selected")

    if len(placeholder_items) > 1:
        raise ValueError("Too many selected nodes")

    placeholder_item = placeholder_items[0]
    window = WorkfileBuildPlaceholderDialog(host, builder,
                                            parent=get_main_window())
    window.set_update_mode(placeholder_item)
    window.exec_()
