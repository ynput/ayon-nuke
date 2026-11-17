from __future__ import annotations

import os
import nuke
import clique
from ayon_core.lib import Logger
log = Logger.get_logger(__name__)

SINGLE_FILE_FORMATS = ['avi', 'mp4', 'mxf', 'mov', 'mpg', 'mpeg', 'wmv', 'm4v',
                       'm2v']


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
        # so this is not an error; the caller tells the user to render first.
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
            # Assemble all files in directory to find the complete sequence
            coll = clique.assemble(
                files_in_dir,
                assume_padded_when_ambiguous=True,
                patterns=[clique.PATTERNS['frames']]
            )[0][0]
            if coll.padding == collection.padding:
                # Found matching sequence
                firstframe = min(coll.indexes)
                lastframe = max(coll.indexes)
                filepath = f"{coll.head}{'#' * coll.padding}{coll.tail}"
    if filepath is None:
        return None, 0, 0
    # Convert to relative path if requested
    if allow_relative and project_dir:
        filepath = os.path.relpath(filepath, project_dir)

    return filepath.replace('\\', '/'), firstframe, lastframe


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
                file_path = n.knob('file').evaluate()
                target_file, firstFrame, lastFrame = detect_file_on_disk(
                    n.knob('file').getValue(),
                    file_path,
                    project_dir,
                    comp_start,
                    allow_relative
                )
                if not target_file:
                    message = (
                        "Cannot create Read node: no rendered files were "
                        f"found at `{file_path}`.\n\n"
                        "Render the Write node first, the render folder and "
                        "the files are created by rendering."
                    )
                    log.warning(message)
                    nuke.message(message)
                    return

                # get node data
                ndata = {
                    'filepath': target_file,
                    'firstframe': int(firstFrame),
                    'lastframe': int(lastFrame),
                    'new_xpos': new_xpos,
                    'new_ypos': new_ypos,
                    'write_frame_mode': str(n.knob('frame_mode').value()),
                    'write_frame': n.knob('frame').value(),
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
