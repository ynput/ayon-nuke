import logging
import contextlib
import nuke

log = logging.getLogger(__name__)


@contextlib.contextmanager
def viewer_update_and_undo_stop():
    """Lock viewer from updating and stop recording undo steps"""
    try:
        # stop active viewer to update any change
        viewer = nuke.activeViewer()
        if viewer:
            viewer.stop()
        else:
            log.warning("No available active Viewer")
        nuke.Undo.disable()
        yield
    finally:
        nuke.Undo.enable()


@contextlib.contextmanager
def undo_chunk(name: str = ""):
    """Context manager to wrap multiple actions into a single undo chunk.

    The name of the undo chunk can either be given when entering the block,
    or updated later using the `nuke.Undo.name(name)` method.

    Args:
        name (str): Name of the undo chunk.

    Examples:
        As a context manager:
        >>> with undo_chunk("Load Image"):
        >>>    # do multiple actions here
        >>>    ...

        As a decorator:
        >>> @undo_chunk("Load Image")
        >>> def load_image():
        >>>    # do multiple actions here
        >>>    ...

    """
    nuke.Undo.begin()
    if name:
        nuke.Undo.name(name)

    try:
        yield
    finally:
        nuke.Undo.end()
