from __future__ import annotations

import os
import nuke
import clique
from ayon_core.lib import Logger
log = Logger.get_logger(__name__)

SINGLE_FILE_FORMATS = ['avi', 'mp4', 'mxf', 'mov', 'mpg', 'mpeg', 'wmv', 'm4v',
                       'm2v']

#: Node label marking a Read that was prepared before its media exists.
PREPARED_LABEL = "not rendered yet"


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
        # so this is not an error; the caller prepares the Read node instead.
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


def _write_render_pattern(write_node):
    """Return the render path pattern of a Write node, or None.

    `nuke.filename` resolves the pattern the way Nuke would read the files
    (including filename filters such as the AyON dirmap) and it works for
    files that do not exist yet.
    """
    file_knob = write_node.knob('file')
    if file_knob is None:
        return None

    pattern = None
    try:
        pattern = nuke.filename(write_node)
    except Exception:
        log.debug(
            "Could not resolve the render path of `%s`",
            write_node.name(), exc_info=True,
        )
    if not pattern:
        pattern = file_knob.getValue()
    if not pattern:
        return None
    return _normalize_path(pattern)


def _write_frame_range(write_node):
    """Return the frame range the Write node is set up to render.

    AyON's render creators set `use_limit` and `first`/`last` from the
    workfile frame range; otherwise the root frame range is used.
    """
    root = nuke.root()
    first_frame = int(root["first_frame"].value())
    last_frame = int(root["last_frame"].value())

    use_limit = write_node.knob("use_limit")
    if use_limit is not None and use_limit.value():
        first_knob = write_node.knob("first")
        last_knob = write_node.knob("last")
        if first_knob is not None and last_knob is not None:
            first_frame = int(first_knob.value())
            last_frame = int(last_knob.value())

    if last_frame < first_frame:
        last_frame = first_frame
    return first_frame, last_frame


def _find_prepared_read(pattern, node_class):
    """Find a Read/DeepRead prepared earlier for the same render pattern."""
    if not pattern:
        return None
    read_class = "DeepRead" if node_class == "DeepWrite" else "Read"
    for read_node in nuke.allNodes(read_class):
        if not (
            read_node.knob("label") is not None
            and read_node.knob("label").value() == PREPARED_LABEL
        ):
            continue
        file_knob = read_node.knob("file")
        if file_knob is None:
            continue
        read_pattern = nuke.filename(read_node)
        if not read_pattern:
            read_pattern = file_knob.getValue()
        if read_pattern and _normalize_path(read_pattern) == pattern:
            return read_node
    return None


def _set_read_data(read_node, ndata, comp_start):
    """Apply the render data to an existing Read/DeepRead node."""
    read_node.knob('file').setValue(ndata['filepath'])
    if ndata.get("node_class") != "DeepWrite":
        read_node.knob('colorspace').setValue(int(ndata['colorspace']))
        read_node.knob('raw').setValue(ndata['rawdata'])
    read_node.knob('first').setValue(int(ndata['firstframe']))
    read_node.knob('last').setValue(int(ndata['lastframe']))
    read_node.knob('origfirst').setValue(int(ndata['firstframe']))
    read_node.knob('origlast').setValue(int(ndata['lastframe']))
    if comp_start == int(ndata['firstframe']):
        read_node.knob('frame_mode').setValue("1")
        read_node.knob('frame').setValue(str(comp_start))
    else:
        read_node.knob('frame_mode').setValue("0")
    read_node.knob('xpos').setValue(ndata['new_xpos'])
    read_node.knob('ypos').setValue(ndata['new_ypos'])


def create_read_node(ndata, comp_start):
    filepath = ndata["filepath"]
    if ndata.get("node_class") == "DeepWrite":
        read = nuke.createNode("DeepRead", f'file "{filepath}"')
    else:
        read = nuke.createNode("Read", f'file "{filepath}"')
    _set_read_data(read, ndata, comp_start)
    nuke.inputs(read, 0)
    return read


def _prepared_read_data(write_node, xpos, ypos, frame_range=None):
    """Build Read node data for a render that does not exist yet."""
    pattern = _write_render_pattern(write_node)
    if not pattern:
        return None

    if frame_range is None:
        frame_range = _write_frame_range(write_node)
    first_frame, last_frame = frame_range
    ndata = {
        'filepath': pattern,
        'firstframe': first_frame,
        'lastframe': last_frame,
        'new_xpos': xpos,
        'new_ypos': ypos,
        'node_class': write_node.Class(),
    }
    if write_node.Class() == "Write":
        ndata.update({
            'colorspace': write_node.knob('colorspace').getValue(),
            'rawdata': write_node.knob('raw').value(),
        })
    return ndata


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
                # Check the start of the intended render range instead of the
                # playhead, so the check does not depend on where the artist
                # is scrubbing.
                frame_range = _write_frame_range(n)
                file_path = n.knob('file').evaluate(frame_range[0])
                target_file, firstFrame, lastFrame = detect_file_on_disk(
                    n.knob('file').getValue(),
                    file_path,
                    project_dir,
                    comp_start,
                    allow_relative
                )
                if target_file:
                    # get node data
                    ndata = {
                        'filepath': target_file,
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
                    group_read_nodes.append((ndata, False))
                else:
                    # Nothing rendered yet; prepare the Read node so it is
                    # ready when the files come alive.
                    ndata = _prepared_read_data(
                        n, new_xpos, new_ypos, frame_range
                    )
                    if ndata:
                        group_read_nodes.append((ndata, True))

    prepared_messages = []
    for ndata, prepared in group_read_nodes:
        # Reuse a Read node prepared by an earlier click for this pattern.
        read_node = _find_prepared_read(
            ndata['filepath'], ndata['node_class']
        )
        if prepared:
            if read_node is None:
                read_node = create_read_node(ndata, comp_start)
            else:
                _set_read_data(read_node, ndata, comp_start)

            label_knob = read_node.knob("label")
            if label_knob is not None:
                label_knob.setValue(PREPARED_LABEL)

            message = (
                "No rendered files were found yet for:\n"
                f"`{ndata['filepath']}`\n\n"
                f"A Read node `{read_node.name()}` is prepared for that path. "
                "Render the Write node first, then press Reload on the Read "
                "node (or click Read From Rendered again) to load the media."
            )
            prepared_messages.append(message)
            continue

        if read_node is not None:
            # The media exists now; promote the prepared node to a real Read.
            _set_read_data(read_node, ndata, comp_start)
            label_knob = read_node.knob("label")
            if label_knob is not None and label_knob.value() == PREPARED_LABEL:
                label_knob.setValue("")

            reload_knob = read_node.knob("reload")
            if reload_knob is not None:
                reload_knob.execute()

        else:
            # create read node
            create_read_node(ndata, comp_start)

    for message in prepared_messages:
        log.warning(message)
        nuke.message(message)
