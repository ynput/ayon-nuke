"""Host API required Work Files tool"""
from __future__ import annotations

import os
import contextlib
import nuke
import shutil
from .constants import ASSIST


@contextlib.contextmanager
def _no_create_callbacks():
    """Context manager to temporarily disable `nuke.onCreate` callbacks."""
    callbacks = nuke.onCreates.copy()
    try:
        nuke.onCreates.clear()
        yield
    finally:
        nuke.onCreates.update(callbacks)


def file_extensions():
    return [".nk"]


def has_unsaved_changes():
    return nuke.root().modified()


def save_file(filepath):
    path = filepath.replace("\\", "/")
    nuke.scriptSaveAs(path, overwrite=1)
    nuke.Root()["name"].setValue(path)
    nuke.Root()["project_directory"].setValue(os.path.dirname(path))
    nuke.Root().setModified(False)


def _get_autosave_filepath(filepath: str) -> str | None:
    """Query autosave file path for a given file path, by evaluating the
    autosave name preferences with root name temporarily set to the given
    file path.

    This allows us to get the autosave path for a file that is not currently
    open in Nuke.
    """
    root = nuke.Root()
    original_name = root.name()
    root["name"].setValue(filepath)
    try:
        autosave = nuke.toNode("preferences")["AutoSaveName"].evaluate()
        if os.path.isfile(autosave):
            return autosave
        return None
    finally:
        root["name"].setValue(original_name)


def open_file(filepath):

    def read_script(nuke_script):
        if not ASSIST:
            with _no_create_callbacks():
                nuke.scriptClear()
            nuke.scriptReadFile(nuke_script)

            root = nuke.Root()
            root["name"].setValue(nuke_script)
            root["project_directory"].setValue(os.path.dirname(nuke_script))
            root.setModified(False)

            # Above way of loading script does not trigger onCreate() nor
            # onScriptLoad() callback, so we need to call it manually here
            # after root name has been set so the callbacks behave similar
            # to how they would if user would do File > Open or on Nuke
            # launch with a comp script file.
            nuke.onCreate()
            nuke.onScriptLoad()
        else:
            nuke.scriptOpen(nuke_script)

    filepath = filepath.replace("\\", "/")

    # Before opening the file, see if it has an autosave file and ask the user
    # if they want to load it instead.
    if nuke.GUI and (autosave := _get_autosave_filepath(filepath)):
        if nuke.ask(
            "Autosave detected.\n"
            "Would you like to load the autosave file?"
        ):
            try:
                # Overwrite the filepath with autosave
                shutil.copy(autosave, filepath)
            except shutil.Error as err:
                nuke.message(
                    f"Detected autosave file could not be used.\n{err}"
                )

    # To remain in the same window, we have to clear the script and read
    # in the contents of the workfile.
    read_script(filepath)

    return True


def current_file():
    current_file = nuke.root().name()

    # Unsaved current file
    if current_file == 'Root':
        return None

    return os.path.normpath(current_file).replace("\\", "/")


def work_root(session):

    work_dir = session["AYON_WORKDIR"]
    scene_dir = session.get("AVALON_SCENEDIR")
    if scene_dir:
        path = os.path.join(work_dir, scene_dir)
    else:
        path = work_dir

    return os.path.normpath(path).replace("\\", "/")
