from __future__ import annotations

import os
import nuke
import clique
from ayon_core.lib import Logger
log = Logger.get_logger(__name__)

SINGLE_FILE_FORMATS = ['avi', 'mp4', 'mxf', 'mov', 'mpg', 'mpeg', 'wmv', 'm4v',
                       'm2v']


def _normalize_path(path):
    """Use forward slashes in a path, like Nuke does."""
    return path.replace('\\', '/')


def detect_file_on_disk(
        k_value: str,
        k_eval: str,
        project_dir: str,
        first_frame: int,
        allow_relative: bool
) -> tuple[str | None, int, int]:
    """Detects a file or image sequence on disk and returns its path along
    with the first and last frame numbers.

    Args:
        k_value (str): The original file path pattern, potentially
        containing frame padding token "%04d".
        k_eval (str): The evaluated file path potentially with a specific
        frame number.
        project_dir (str): The root directory of the project.
        first_frame (int): The first frame number to consider when detecting
        the file sequence.
        allow_relative (bool): Whether to return the file path as relative to
        the project directory.

    Returns:
        tuple[str, int, int] | None: A tuple containing the file path,
        first frame number, and last frame number if the file or sequence
        is detected; otherwise, None.
    """
    combined_relative_path = None
    filepath = None
    firstframe = first_frame
    lastframe = first_frame
    if not k_eval or not os.path.exists(k_eval):
        # The render folder and the rendered files are created by rendering,
        # so this is not an error; the caller points the Read at the path.
        return None, 0, 0
    combined_relative_path = os.path.abspath(
        os.path.join(project_dir or "", k_eval)
    )
    directory = os.path.dirname(k_eval)
    if directory and not os.path.isdir(directory):
        return None, 0, 0

    # Handle single file case (no frame padding)
    if k_eval == k_value:
        # If the evaluated path is the same as the original pattern,
        # this means it does not contain any frame token
        if os.path.exists(k_eval):
            filepath = k_eval

        elif project_dir is not None:
            # Try with project directory
            combined_path = os.path.abspath(os.path.join(project_dir, k_eval))
            if os.path.exists(combined_path):
                filepath = combined_path

        if filepath and allow_relative and project_dir is not None:
            filepath = os.path.relpath(filepath, project_dir)

        return filepath, firstframe, lastframe

    collections, _ = clique.assemble(
        [combined_relative_path],
        assume_padded_when_ambiguous=True,
        minimum_items=1,
        patterns=[clique.PATTERNS['frames']]
    )

    collection = collections[0] if collections else None
    if collection:
        # Get all files in the directory to find all frames
        files_in_dir = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f))
        ]

        if files_in_dir:
            # Assemble all files in directory to find the complete sequence.
            # A single rendered frame (image product) is a valid sequence.
            collections_in_dir, _ = clique.assemble(
                files_in_dir,
                assume_padded_when_ambiguous=True,
                minimum_items=1,
                patterns=[clique.PATTERNS['frames']]
            )
            coll = collections_in_dir[0] if collections_in_dir else None
            if coll is not None and coll.padding == collection.padding:
                # Found matching sequence
                firstframe = min(coll.indexes)
                lastframe = max(coll.indexes)
                filepath = f"{coll.head}{'#' * coll.padding}{coll.tail}"
    if filepath is None:
        return None, 0, 0
    # Convert to relative path if requested
    if allow_relative and project_dir:
        filepath = os.path.relpath(filepath, project_dir)

    return _normalize_path(filepath), firstframe, lastframe


def _write_frame_range(write_node):
    """Return the frame range the Write node is set up to render.

    AYON's render creators set `use_limit` and `first`/`last` from the
    workfile frame range; otherwise the root frame range is used.
    """
    root = nuke.root()
    first_frame = int(root["first_frame"].value())
    last_frame = int(root["last_frame"].value())

    use_limit = write_node.knob("use_limit")
    if use_limit is not None and use_limit.value():
        first_frame = int(write_node.knob("first").value())
        last_frame = int(write_node.knob("last").value())

    return first_frame, max(first_frame, last_frame)


def create_read_node(ndata, comp_start):
    filepath = ndata["filepath"]
    if ndata.get("node_class") == "DeepWrite":
        read = nuke.createNode("DeepRead", f'file "{filepath}"')
    else:
        read = nuke.createNode("Read", f'file "{filepath}"')
        read.knob('colorspace').setValue(int(ndata['colorspace']))
        read.knob('raw').setValue(ndata['rawdata'])
    read.knob('first').setValue(int(ndata['firstframe']))
    read.knob('last').setValue(int(ndata['lastframe']))
    read.knob('origfirst').setValue(int(ndata['firstframe']))
    read.knob('origlast').setValue(int(ndata['lastframe']))
    if comp_start == int(ndata['firstframe']):
        read.knob('frame_mode').setValue("1")
        read.knob('frame').setValue(str(comp_start))
    else:
        read.knob('frame_mode').setValue("0")
    read.knob('xpos').setValue(ndata['new_xpos'])
    read.knob('ypos').setValue(ndata['new_ypos'])
    nuke.inputs(read, 0)
    return


def write_to_read(gn,
                  allow_relative=False):

    comp_start = nuke.Root().knob('first_frame').value()
    project_dir = nuke.Root().knob('project_directory').getValue()
    if not project_dir or not os.path.exists(project_dir):
        # Nuke can evaluate the project directory to `None` (issue #427).
        project_dir = nuke.Root().knob('project_directory').evaluate() or ""

    group_read_nodes = []
    not_rendered = []
    with gn:
        height = gn.screenHeight()  # get group height and position
        new_xpos = int(gn.knob('xpos').value())
        new_ypos = int(gn.knob('ypos').value()) + height + 20
        group_writes = [
            n for n in nuke.allNodes() if n.Class() in {"Write", "DeepWrite"}
        ]
        if group_writes != []:
            # there can be only 1 write node, taking first
            n = group_writes[0]

            if n.knob('file') is not None:
                # Check the first frame of the render range, not the
                # playhead, so the result does not depend on scrubbing.
                frame_range = _write_frame_range(n)
                myfile, firstFrame, lastFrame = detect_file_on_disk(
                    n.knob('file').getValue(),
                    n.knob('file').evaluate(frame_range[0]),
                    project_dir,
                    comp_start,
                    allow_relative
                )
                if not myfile:
                    # Nothing rendered yet (the render folder may not exist
                    # either): point the Read at the render path, Nuke loads
                    # the media on Reload once it is rendered.
                    myfile = _normalize_path(n.knob('file').getValue())
                    firstFrame, lastFrame = frame_range
                    not_rendered.append(myfile)

                # get node data
                ndata = {
                    'filepath': myfile,
                    'firstframe': int(firstFrame),
                    'lastframe': int(lastFrame),
                    'new_xpos': new_xpos,
                    'new_ypos': new_ypos,
                    'node_class': n.Class(),
                }
                if n.Class() == "Write":
                    ndata.update({
                        'colorspace': n.knob('colorspace').getValue(),
                        'rawdata': n.knob('raw').value(),
                    })
                group_read_nodes.append(ndata)

    # create reads in one go
    for oneread in group_read_nodes:
        # create read node
        create_read_node(oneread, comp_start)

    if not_rendered:
        message = (
            "Nothing is rendered yet for:\n{}\n\n"
            "The Read node points to the render path. Render the Write "
            "node, then press Reload on the Read node."
        ).format("\n".join(not_rendered))
        log.warning(message)
        nuke.message(message)
