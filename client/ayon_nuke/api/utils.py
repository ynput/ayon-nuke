from __future__ import annotations

from dataclasses import dataclass
import os

import nuke

import pyblish.util
import pyblish.api

from ayon_core import resources
from ayon_core.lib import Logger
from ayon_core.lib.transcoding import VIDEO_EXTENSIONS
from ayon_core.pipeline import registered_host
from ayon_core.pipeline.create import CreateContext

log = Logger.get_logger(__name__)


def render_single_frame(group_node: nuke.Node) -> None:
    """Render a single frame for the given group node.

    Args:
        group_node (nuke.Node): The group node containing the write
        node to render.
    """
    write_node = nuke.allNodes("Write", group=group_node)[0]
    frame = int(write_node["first"].value())
    nuke.execute(write_node.fullName(), frame, frame)


def get_write_frame_range(write_node: nuke.Node) -> tuple[int, int]:
    """Return the frame range a Write or DeepWrite node renders.

    The node's own range when `use_limit` is on (AYON's render creators set
    it from the workfile), otherwise the workfile frame range.
    """
    root = nuke.root()
    first_frame = int(root["first_frame"].value())
    last_frame = int(root["last_frame"].value())
    if write_node["use_limit"].value():
        first_frame = int(write_node["first"].value())
        last_frame = int(write_node["last"].value())
    return first_frame, last_frame


def _get_render_write_node(group_node: nuke.Node) -> nuke.Node | None:
    """Return the Write or DeepWrite node of a render group, if any."""
    for node in group_node.nodes():
        if node.Class() in {"Write", "DeepWrite"}:
            return node
    return None


def _get_rendered_media(
    write_node: nuke.Node
) -> tuple[str, int, int, int | None, bool]:
    """Return what a Read node needs to load the Write node's render.

    Returns:
        tuple: file path, first and last frame of the Read, the frame a movie
            starts at in the comp (None for images) and whether the media
            exists on disk.
    """
    first_frame, last_frame = get_write_frame_range(write_node)
    last_frame = max(first_frame, last_frame)
    file_knob = write_node["file"]
    first_path = file_knob.evaluate(first_frame) or ""

    ext = os.path.splitext(first_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        # A movie is one file whose frames count from 1. With a frame token
        # in the path Nuke names it after the first frame
        # (`render.####.mov` writes `render.1001.mov`).
        return (
            first_path,
            1,
            last_frame - first_frame + 1,
            first_frame,
            os.path.isfile(first_path),
        )

    if first_path == file_knob.evaluate(first_frame + 1):
        # One image without a frame token (e.g. a still image product).
        return (
            first_path, first_frame, first_frame, None,
            os.path.isfile(first_path),
        )

    # An image sequence: read the frames of the render range that exist,
    # or the whole range when nothing is rendered yet.
    rendered_frames = [
        frame
        for frame in range(first_frame, last_frame + 1)
        if os.path.isfile(file_knob.evaluate(frame))
    ]
    if rendered_frames:
        first_frame, last_frame = rendered_frames[0], rendered_frames[-1]
    pattern = nuke.filename(write_node) or file_knob.value()
    return (
        pattern.replace("\\", "/"),
        first_frame,
        last_frame,
        None,
        bool(rendered_frames),
    )


def _get_parent(node: nuke.Node) -> nuke.Node:
    """Return the group (or root) that contains `node`."""
    parent_path = node.fullName().rpartition(".")[0]
    if not parent_path:
        return nuke.root()
    # `toNode` looks names up in the current group: start from the root.
    with nuke.root():
        return nuke.toNode(parent_path)


def read_from_rendered(group_node: nuke.Node) -> nuke.Node | None:
    """Create a Read node for the media rendered by a render group.

    The `Read From Rendered` button of AYON's render groups. The Read node
    gets the Write node's colorspace and the rendered frame range; a movie
    starts at the first frame of the render range. When nothing is
    rendered yet the Read node points to the render path and the artist is
    asked to press Reload on it after rendering.

    Args:
        group_node (nuke.Node): Render group with a Write or DeepWrite node.

    Returns:
        nuke.Node | None: The created Read or DeepRead node.
    """
    write_node = _get_render_write_node(group_node)
    if write_node is None:
        return None

    file_path, first, last, movie_start, exists = (
        _get_rendered_media(write_node)
    )

    # A button runs inside its group: create the Read next to the group.
    read_class = "DeepRead" if write_node.Class() == "DeepWrite" else "Read"
    with _get_parent(group_node):
        read_node = nuke.createNode(
            read_class, f'file "{file_path}"', inpanel=False
        )

    if read_class == "Read":
        # Imported here: `plugin` imports `lib`, which imports this module.
        from .plugin import get_colorspace_from_node

        read_node["colorspace"].setValue(
            get_colorspace_from_node(write_node)
        )
        read_node["raw"].setValue(write_node["raw"].value())

    # Nuke reads the range of an existing movie itself.
    if movie_start is None or not exists:
        for knob_name, value in (
            ("first", first), ("origfirst", first),
            ("last", last), ("origlast", last),
        ):
            read_node[knob_name].setValue(int(value))

    comp_start = int(nuke.root()["first_frame"].value())
    start_frame = movie_start
    if start_frame is None and first == comp_start:
        start_frame = comp_start
    if start_frame is None:
        read_node["frame_mode"].setValue("0")
    else:
        read_node["frame_mode"].setValue("1")
        read_node["frame"].setValue(str(start_frame))

    read_node["xpos"].setValue(int(group_node["xpos"].value()))
    read_node["ypos"].setValue(
        int(group_node["ypos"].value()) + group_node.screenHeight() + 20
    )
    nuke.inputs(read_node, 0)

    if not exists:
        message = (
            f"Nothing is rendered yet for:\n{file_path}\n\n"
            "The Read node points to the render path. Render the Write "
            "node, then press Reload on the Read node."
        )
        log.warning(message)
        nuke.message(message)
    return read_node


def clear_rendered(dir_path: str) -> None:
    """Delete the files in a render folder."""
    for file_name in os.listdir(dir_path):
        file_path = os.path.join(dir_path, file_name)
        log.info("Removing: `{}`".format(file_path))
        os.remove(file_path)


def clear_rendered_from_node(node: nuke.Node) -> None:
    """Delete the rendered files of a Write node or of a group's Writes.

    The `Clear Rendered` button of AYON's render groups.
    """
    node_class = node.Class()
    if node_class == "Write":
        clear_rendered(os.path.dirname(node["file"].evaluate()))
        return

    if node_class == "Group":
        for child in node.nodes():
            clear_rendered_from_node(child)
        return

    log.error(f"Unsupported node class: `{node_class}`")


@dataclass(frozen=True)
class FavoriteDef:
    name: str
    path: str


def set_context_favorites(favorites: list[FavoriteDef]) -> None:
    """Adding favorite folders to nuke's browser

    Args:
        favorites (list[FavoriteDef]): list of favorite definitions

    """
    icon_path = resources.get_resource("icons", "folder-favorite.png")
    for favorite in favorites:
        nuke.addFavoriteDir(
            favorite.name,
            favorite.path,
            nuke.IMAGE | nuke.SCRIPT | nuke.GEO,
            icon=icon_path
        )


def get_node_outputs(node):
    """
    Return a dictionary of the nodes and pipes that are connected to node
    """
    dep_dict = {}
    dependencies = node.dependent(nuke.INPUTS | nuke.HIDDEN_INPUTS)
    for d in dependencies:
        dep_dict[d] = []
        for i in range(d.inputs()):
            if d.input(i) == node:
                dep_dict[d].append(i)
    return dep_dict


def is_node_gizmo(node) -> bool:
    """Return True if the node is a gizmo."""
    return node.knob('gizmo_file') is not None


def gizmo_is_nuke_default(gizmo) -> bool:
    """Check if gizmo is in default install path"""
    plug_dir = os.path.join(os.path.dirname(
        nuke.env['ExecutablePath']), 'plugins')
    return gizmo.filename().startswith(plug_dir)


def bake_gizmos_recursively(in_group=None):
    """Converting a gizmo to group

    Arguments:
        in_group (Optional[nuke.Node]): group node or all nodes
    """
    from .lib import maintained_selection
    if in_group is None:
        in_group = nuke.Root()
    # preserve selection after all is done
    with maintained_selection():
        # jump to the group
        with in_group:
            for node in nuke.allNodes():
                if is_node_gizmo(node) and not gizmo_is_nuke_default(node):
                    with node:
                        outputs = get_node_outputs(node)
                        group = node.makeGroup()
                        # Reconnect inputs and outputs if any
                        if outputs:
                            for n, pipes in outputs.items():
                                for i in pipes:
                                    n.setInput(i, group)
                        for i in range(node.inputs()):
                            group.setInput(i, node.input(i))
                        # set node position and name
                        group.setXYpos(node.xpos(), node.ypos())
                        name = node.name()
                        nuke.delete(node)
                        group.setName(name)
                        node = group

                if node.Class() == "Group":
                    bake_gizmos_recursively(node)


def submit_render_on_farm(node):
    # Ensure code is executed in root context.
    if nuke.root() == nuke.thisNode():
        _submit_render_on_farm(node)
    else:
        # If not in root context, move to the root context and then execute the
        # code.
        with nuke.root():
            _submit_render_on_farm(node)


def _submit_render_on_farm(node) -> bool:
    """Render on farm submission

    This function prepares the context for farm submission, validates it,
    extracts relevant data, copies the current workfile to a timestamped copy,
    and submits the job to the farm.

    Args:
        node (Node): The node for which the farm submission is being made.

    Returns:
        bool: Did the submission succeed?
    """

    host = registered_host()
    create_context = CreateContext(host)

    # Ensure CreateInstance is enabled and renders on farm.
    for instance in create_context.instances:
        is_current_node = node is instance.transient_data["node"]

        if not instance.is_mandatory:
            instance.data["active"] = is_current_node

        if is_current_node:
            instance.data["creator_attributes"]["render_target"] = "farm"

    context = pyblish.api.Context()
    context.data["create_context"] = create_context
    # Used in pyblish plugin to determine which instance to publish.
    context.data["node_name"] = node.name()
    # Used in pyblish plugins to determine whether to run or not.
    context.data["render_on_farm"] = True

    # Since we need to bypass version validation and incrementing, we need to
    # remove the plugins from the list that are responsible for these tasks.
    plugins = pyblish.api.discover()
    blacklist = ["IncrementScriptVersion", "ValidateVersion"]
    plugins = [
        plugin
        for plugin in plugins
        if plugin.__name__ not in blacklist
    ]

    context = pyblish.util.publish(context, plugins=plugins)

    error_message = ""
    success = True
    for result in context.data["results"]:
        if result["success"]:
            continue

        success = False

        err = result["error"]
        error_message += "\n"
        error_message += err.formatted_traceback

    if nuke.GUI:
        from ayon_core.tools.utils import show_message_dialog
        if success:
            show_message_dialog(
                "Submission Successful",
                "Submission to the farm was successful."
            )
        else:
            show_message_dialog(
                 "Publish Errors",
                 error_message, level="critical"
            )

    return success
