import nuke
import os
import read_node_utils
import platform

from ayon_core.pipeline import install_host
from ayon_nuke.api import NukeHost

from ayon_core.lib import Logger
from ayon_nuke import api
from ayon_nuke.api.lib import (
    on_script_load,
    check_inventory_versions,
    WorkfileSettings,
    dirmap_file_name_filter,
    add_scripts_gizmo,
    create_write_node,
)
from pathlib import Path
from ayon_core.settings import get_project_settings
from ayon_core.tools.utils.host_tools import show_publisher

"""
I've begun moving quick_write functions into their own file,
but you have to be careful because function calls embedded as 
strings in old nodes will break if they are not available
directly in this scope, and old nuke scripts will break
"""
from quick_write import (
    quick_write_node,
    _quick_write_node,
    embedOptions,
    presets,
    set_hwrite_version,
    ovs_write_node,
)
from view_manager import show as show_view_manager
from hornet_publish_utils import quick_publish

from hornet_deadline_utils import (
    deadlineNetworkSubmit,
    save_script_with_render,
)


host = NukeHost()
install_host(host)

log = Logger.get_logger(__name__)


def apply_format_presets():
    # print("apply_format_presets")
    node = nuke.thisNode()
    knob = nuke.thisKnob()
    if knob.name() == "file_type":
        if knob.value() in presets.keys():
            for preset in presets[knob.value()]:
                if node.knob(preset[0]):
                    node.knob(preset[0]).setValue(preset[1])


# Hornet- helper to switch file extension to filetype
def writes_ver_sync():
    """Callback synchronizing version of publishable write nodes"""
    try:
        print("Hornet- syncing version to write nodes")
        # rootVersion = pype.get_version_from_path(nuke.root().name())
        pattern = re.compile(r"[\._]v([0-9]+)", re.IGNORECASE)
        rootVersion = pattern.findall(nuke.root().name())[0]
        padding = len(rootVersion)
        new_version = "v" + str("{" + ":0>{}".format(padding) + "}").format(
            int(rootVersion)
        )
        print("new_version: {}".format(new_version))
    except Exception as e:
        print(e)
        return
    groupnodes = [
        node.nodes() for node in nuke.allNodes() if node.Class() == "Group"
    ]
    allnodes = [
        node for group in groupnodes for node in group
    ] + nuke.allNodes()
    for each in allnodes:
        if each.Class() == "Write":
            # check if the node is avalon tracked
            if each.name().startswith("inside_"):
                avalonNode = nuke.toNode(each.name().replace("inside_", ""))
            else:
                avalonNode = each
            if "AvalonTab" not in avalonNode.knobs():
                print("tab failure")
                continue

            avalon_knob_data = avalon.nuke.get_avalon_knob_data(
                avalonNode, ["avalon:", "ak:"]
            )
            try:
                if avalon_knob_data["families"] not in ["render", "write"]:
                    print("families fail")
                    log.debug(avalon_knob_data["families"])
                    continue

                node_file = each["file"].value()

                # node_version = "v" + pype.get_version_from_path(node_file)
                node_version = "v" + pattern.findall(node_file)[0]

                log.debug("node_version: {}".format(node_version))

                node_new_file = node_file.replace(node_version, new_version)
                each["file"].setValue(node_new_file)
                # H: don't need empty folders if work file isn't rendered later
                # if not os.path.isdir(os.path.dirname(node_new_file)):
                #    log.warning("Path does not exist! I am creating it.")
                #    os.makedirs(os.path.dirname(node_new_file), 0o766)
            except Exception as e:
                print(e)
                log.warning(
                    "Write node: `{}` has no version in path: {}".format(
                        each.name(), e
                    )
                )


def switchExtension():
    # print("switchExtension")
    nde = nuke.thisNode()
    knb = nuke.thisKnob()
    if knb == nde.knob("file_type"):
        filek = nde.knob("file")
        old = filek.value()
        pre, ext = os.path.splitext(old)
        filek.setValue(pre + "." + knb.value())


def check_and_show_publisher():
    # this is supposed to check if there's already a publish to save the user
    # from submitting one that fails, but the assemble_publish_path() function
    # doest not currently take version into account and just returns the latest
    # which causes this to return false positive.

    # Leaving it here because it's on the list to make a btter pubklish bath
    # solver, at which point this function will work.

    # publish_path = read_node_utils.assemble_publish_path(nuke.thisNode())

    # if publish_path:
    #     base = publish_path.name.split(".")[0]
    #     if publish_path.parent.glob(f"{base}.*"):
    #         if not nuke.ask("Files exist in publish location. Conitue?"):
    #             return

    from ayon_core.tools.utils import host_tools

    host_tools.show_publisher(tab="Publish")


def enable_disable_frame_range():
    # print("enable_disable_frame_range")
    nde = nuke.thisNode()
    knb = nuke.thisKnob()
    if not nde.knob("use_limit") or not knb.name() == "use_limit":
        return
    group = nuke.toNode(".".join(["root"] + nde.fullName().split(".")[:-1]))
    enable = nde.knob("use_limit").value()
    group.knobs()["first"].setEnabled(enable)
    group.knobs()["last"].setEnabled(enable)

def submit_selected_write():
    for nde in nuke.selectedNodes():
        if nde.Class() == "Write":
            submit_write(nde)

def enable_publish_range():
    # print("enable_publish_range")

    nde = nuke.thisNode()
    kb = nuke.thisKnob()

    if not kb == nde.knob("usePublishRange"):
        return
    print("oh no!")
    if kb.value():
        nde.knob("publishFirst").setEnabled(True)
        nde.knob("publishLast").setEnabled(True)
    else:
        nde.knob("publishFirst").setEnabled(False)
        nde.knob("publishLast").setEnabled(False)

hornet_menu = nuke.menu("Nuke")
m = hornet_menu.addMenu("&Hornet")
m.addCommand("&Quick Write Node", "quick_write_node()", "Ctrl+W")
m.addCommand(
    "&Quick PreWrite Node",
    "quick_write_node(family='prerender')",
    "Ctrl+Shift+W",
)

m.addCommand("&Oversized Write Node", "ovs_write_node()")
nuke.addKnobChanged(apply_format_presets, nodeClass="Write")
nuke.addKnobChanged(switchExtension, nodeClass="Write")
nuke.addKnobChanged(embedOptions, nodeClass="Write")
nuke.addKnobChanged(enable_publish_range, nodeClass="Group")
nuke.addKnobChanged(enable_disable_frame_range, nodeClass="Write")
nuke.addOnScriptSave(set_hwrite_version)
nuke.addOnScriptSave(writes_ver_sync)
nuke.addOnScriptLoad(WorkfileSettings().set_colorspace)
nuke.addOnCreate(WorkfileSettings().set_colorspace, nodeClass="Root")

### View Manager

toolbar = nuke.toolbar("Nodes")
toolbar.addCommand("Alex Dev / View Manager", "show_view_manager()")


### Project Gizmos

PROJECT_NAME = os.environ["AYON_PROJECT_NAME"]

from node_manager import NodeLoader

nodes_toolbar = nuke.toolbar("Nodes")
project_toolbar = nodes_toolbar.addMenu(PROJECT_NAME)

node_loader = NodeLoader()

project_toolbar.addCommand(
    name="Add Selected Nodes", command="node_loader.add_selected_nodes()"
)
project_toolbar.addCommand(
    name="Add Toolset", command="node_loader.add_toolset()"
)
project_toolbar.addCommand(name="Reload", command="node_loader.populate()")
