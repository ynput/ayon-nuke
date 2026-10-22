from collections import defaultdict
import shutil
import os

from ayon_api import get_project, get_folder_by_id, get_task_by_id
from ayon_core.settings import get_project_settings
from ayon_core.pipeline import Anatomy, registered_host
from ayon_core.pipeline.template_data import get_template_data
from ayon_core.pipeline.workfile import get_workdir_with_workdir_data

from .utils import bake_gizmos_recursively

import nuke


def bake_container(container):
    """Bake containers to read nodes."""

    # Imported here, because the pipeline module imports this module
    from .pipeline import remove_container_data

    node = container["node"]

    # Knob that the loader uses to track the members of the container
    container_id_knob = node.knob("containerId")
    if container_id_knob is not None:
        node.removeKnob(container_id_knob)

    remove_container_data(node)

    node["tile_color"].setValue(0)


def main():
    if not nuke.GUI:
        raise RuntimeError("Invalid in non-GUI mode.")

    from ayon_core.tools import context_dialog
    context = context_dialog.ask_for_context()

    if context is None:
        return

    # Get workfile path to save to.
    project_name = context["project_name"]
    project = get_project(project_name)
    folder = get_folder_by_id(project_name, context["folder_id"])
    task = get_task_by_id(project_name, context["task_id"])
    host = registered_host()
    project_settings = get_project_settings(project_name)
    anatomy = Anatomy(project_name)

    workdir_data = get_template_data(
        project, folder, task, host.name, project_settings
    )

    workdir = get_workdir_with_workdir_data(
        workdir_data,
        project_name,
        anatomy,
        project_settings=project_settings
    )
    # Save current workfile.
    current_file = host.get_current_workfile()
    host.save_workfile(current_file)

    for container in host.ls():
        bake_container(container)

    # Bake gizmos.
    bake_gizmos_recursively()

    # Copy all read node files to "resources" folder next to workfile and
    # change file path.
    first_frame = int(nuke.root()["first_frame"].value())
    last_frame = int(nuke.root()["last_frame"].value())
    files_by_node_name = defaultdict(set)
    nodes_by_name = {}
    for count in range(first_frame, last_frame + 1):
        nuke.frame(count)
        for node in nuke.allNodes(filter="Read"):
            files_by_node_name[node.name()].add(
                nuke.filename(node, nuke.REPLACE)
            )
            nodes_by_name[node.name()] = node

    resources_dir = os.path.join(workdir, "resources")
    for name, files in files_by_node_name.items():
        dir = os.path.join(resources_dir, name)
        if not os.path.exists(dir):
            os.makedirs(dir)

        for f in files:
            shutil.copy(f, os.path.join(dir, os.path.basename(f)))

        node = nodes_by_name[name]
        path = node["file"].value().replace(os.path.dirname(f), dir)
        node["file"].setValue(path.replace("\\", "/"))

    # Save current workfile to new context.
    pushed_workfile = os.path.join(
        workdir, os.path.basename(current_file))
    host.save_workfile(pushed_workfile)

    # Open current context workfile.
    host.open_workfile(current_file)

    nuke.message(f"Pushed to project: \n{pushed_workfile}")
