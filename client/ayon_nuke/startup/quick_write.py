import nuke
import os
from ayon_nuke import api
import json
from ayon_core.lib import Logger

from ayon_nuke.api.lib import (
    create_write_node,
    INSTANCE_DATA_KNOB,
    handle_pub_version,
    get_version_from_path,
    is_version_file_linked,
    incriment_pub_version,
    get_ovs_pathing,
    get_node_data
)

try:
    import nukescripts
except ImportError:
    nukescripts = None


log = Logger.get_logger(__name__)

# dict mapping extension to list of exposed parameters from write node to top level group node
knobMatrix = {
    "exr": ["autocrop", "datatype", "heroview", "metadata", "interleave"],
    "png": ["datatype"],
    "dpx": ["datatype"],
    "tiff": ["datatype", "compression"],
    "jpeg": [],
}

universalKnobs = ["colorspace", "views"]

knobMatrix = {key: universalKnobs + value for key, value in knobMatrix.items()}
presets = {
    "exr": [
        ("colorspace", "ACES - ACEScg"),
        ("channels", "all"),
        ("datatype", "16 bit half"),
    ],
    "png": [
        ("colorspace", "Output - Rec.709"),
        ("channels", "rgba"),
        ("datatype", "16 bit"),
    ],
    "dpx": [
        ("colorspace", "Output - Rec.709"),
        ("channels", "rgb"),
        ("datatype", "10 bit"),
        ("big endian", True),
    ],
    "jpeg": [("colorspace", "Output - sRGB"), ("channels", "rgb")],
}


def quick_write_node(family="render"):
    variant = nuke.getInput("Variant for Quick Write Node", "Main").title()
    _quick_write_node(variant, family, inpanel=True)


def ovs_write_node(family="render"):
    variant = nuke.getInput("Variant for Emergency Write Node", "Main").title()
    _quick_write_node(variant, family, is_ovs=True)


def _quick_write_node(variant, family="render", is_ovs=False, inpanel=True):
    """
    Separated this from the nuke.getInput call to allow calls from other scripts,
    such as a loop in the Kroger versioning script
    """

    if not os.path.exists(nuke.Root().name()):
        nuke.message("You must save script first")
        return

    variant = variant.title()

    nuke.tprint("quick write node")

    if "/" in os.environ["AYON_FOLDER_PATH"]:
        ayon_asset_name = os.environ["AYON_FOLDER_PATH"].split("/")[-1]
    else:
        ayon_asset_name = os.environ["AYON_FOLDER_PATH"]

    # ayon_asset_name = os.environ["AYON_FOLDER_PATH"]
    folder_path = os.environ["AYON_FOLDER_PATH"]
    print(type(folder_path))

    if any(
        var is None or var == ""
        for var in [os.environ["AYON_TASK_NAME"], ayon_asset_name]
    ):
        nuke.alert(
            "missing AYON_TASK_NAME and AYON_FOLDER_PATH, can't make quick write"
        )

    # variant = nuke.getInput('Variant for Quick Write Node','Main').title()
    variant = "_" + variant if variant[0] != "_" else variant

    for existing_variants in [
        parse_publish_instance(node)["variant"]
        for node in get_all_ayon_write_nodes()
    ]:
        if variant == existing_variants:
            nuke.message("Variant already exists")
            return

    if variant == "_" or variant == None or variant == "":
        nuke.message("No Variant Specified, will not create Write Node")
        return
    for nde in nuke.allNodes("Write"):
        if (
            nde.knob("name").value()
            == family + os.environ["AYON_TASK_NAME"] + variant
        ):
            nuke.message("Write Node already exists")
            return
    data = {
        "subset": family + os.environ["AYON_TASK_NAME"] + variant,
        "variant": variant,
        "id": "pyblish.avalon.instance",
        "creator": f"create_write_{family}",
        "creator_identifier": f"create_write_{family}",
        "folderPath": ayon_asset_name,
        "task": os.environ["AYON_TASK_NAME"],
        "productType": family,
        "task": {"name": os.environ["AYON_TASK_NAME"]},
        "productName": family + os.environ["AYON_TASK_NAME"] + variant,
        "hierarchy": "/".join(os.environ["AYON_FOLDER_PATH"].split("/")[:-1]),
        "folder": {"name": os.environ["AYON_FOLDER_PATH"].split("/")[-1]},
        "fpath_template": "{work}/renders/nuke/{subset}/{subset}.{frame}.{ext}",
        "is_ovs": is_ovs,
    }
    qnode = create_write_node(
        family + os.environ["AYON_TASK_NAME"] + variant,
        data,
        prerender=True if family == "prerender" else False,
        inpanel=inpanel,
    )

    qnode = nuke.toNode(family + os.environ["AYON_TASK_NAME"] + variant)
    print(f"Created Write Node: {qnode.name()}")
    data["folderPath"] = os.environ["AYON_FOLDER_PATH"]
    api.set_node_data(qnode, api.INSTANCE_DATA_KNOB, data)
    instance_data = json.loads(qnode.knob(api.INSTANCE_DATA_KNOB).value()[7:])
    instance_data.pop("version", None)
    instance_data["task"] = os.environ["AYON_TASK_NAME"]
    instance_data["creator_attributes"] = {
        "render_taget": "frames_farm",
        "review": True,
    }
    instance_data["publish_attributes"] = {
        "CollectFramesFixDef": {"frames_to_fix": "", "rewrite_version": False},
        "ValidateCorrectAssetContext": {"active": True},
        "NukeSubmitDeadline": {
            "priority": 95,
            "chunk": 1,
            "concurrency": 1,
            "use_gpu": True,
            "suspend_publish": False,
            "workfile_dependency": True,
            "use_published_workfile": True,
        },
    }
    qnode.knob(api.INSTANCE_DATA_KNOB).setValue(
        "JSON:::" + json.dumps(instance_data)
    )
    if family == "prerender":
        qnode.knob("tile_color").setValue(2880113407)
    with qnode.begin():
        inside_write = nuke.toNode(
            "inside_" + family + os.environ["AYON_TASK_NAME"] + variant.title()
        )
        inside_write.knob("file_type").setValue("exr")

    return qnode


DONT_DELETE = [
    api.INSTANCE_DATA_KNOB,
    # "experimental",
    # "quick_publish",
    # "generate_review_media",
    # "generate_review_media_on_farm",
    # "publish_on_farm",
    # "burnin",
]


def embedOptions():
    nde = nuke.thisNode()
    knb = nuke.thisKnob()

    # log.info(' knob of type' + str(knb.Class()))
    htab = nuke.Tab_Knob("htab", "Hornet")
    htab.setName("htab")
    if knb == nde.knob("file_type"):
        group = nuke.toNode(
            ".".join(["root"] + nde.fullName().split(".")[:-1])
        )
        ftype = knb.value()
    else:
        return
    if ftype not in knobMatrix.keys():
        return
    for knb in group.allKnobs():
        try:
            # never clear or touch the invisible string knob that contains the pipeline JSON data
            # if knb.name() != api.INSTANCE_DATA_KNOB:
            if knb.name() not in DONT_DELETE:
                if knb.name() == api.INSTANCE_DATA_KNOB:
                    print("warning you are deleting the instance data knob!")
                    continue
                group.removeKnob(knb)
        except:
            continue

    # Expose publish knobs based on emergency status
    if INSTANCE_DATA_KNOB in group.knobs():
        data = json.loads(
            group.knobs()[INSTANCE_DATA_KNOB].value().replace("JSON:::", "", 1)
        )
        
        if "is_ovs" in data.keys():
            is_ovs = data["is_ovs"]
        else:
            is_ovs = False
    else:
        is_ovs = False

    beginGroup = nuke.Tab_Knob("beginoutput", "Output", nuke.TABBEGINGROUP)
    group.addKnob(beginGroup)

    if "file" not in group.knobs().keys():
        fle = nuke.Multiline_Eval_String_Knob("File output")
        fle.setText(nde.knob("file").value())
        group.addKnob(fle)
        link = nuke.Link_Knob("channels")
        link.makeLink(nde.name(), "channels")
        link.setName("channels")
        group.addKnob(link)
        if "file_type" not in group.knobs().keys():
            link = nuke.Link_Knob("file_type")
            link.makeLink(nde.name(), "file_type")
            link.setName("file_type")
            link.setFlag(0x1000)
            group.addKnob(link)
        for kname in knobMatrix[ftype]:
            link = nuke.Link_Knob(kname)
            link.makeLink(nde.name(), kname)
            link.setName(kname)
            link.setFlag(0x1000)
            group.addKnob(link)
    log.info("links made")

    renderFirst = nuke.Link_Knob("first")
    renderFirst.makeLink(nde.name(), "first")
    renderFirst.setName("Render Start")

    renderLast = nuke.Link_Knob("last")
    renderLast.makeLink(nde.name(), "last")
    renderLast.setName("Render End")

    publishFirst = nuke.Int_Knob("publishFirst", "Publish Start")
    publishLast = nuke.Int_Knob("publishLast", "Publish End")

    usePublishRange = nuke.Boolean_Knob(
        "usePublishRange", "My Publish Range is different from my render range"
    )

    nde.knob("first").setValue(nuke.root().firstFrame())
    nde.knob("last").setValue(nuke.root().lastFrame())
    publishFirst.setValue(nuke.root().firstFrame())
    publishLast.setValue(nuke.root().lastFrame())
    publishFirst.setEnabled(False)
    publishLast.setEnabled(False)
    usePublishRange.setValue(False)

    endGroup = nuke.Tab_Knob("endoutput", None, nuke.TABENDGROUP)
    group.addKnob(endGroup)
    beginGroup = nuke.Tab_Knob(
        "beginpipeline", "Rendering and Pipeline", nuke.TABBEGINGROUP
    )
    group.addKnob(beginGroup)
    group.addKnob(renderFirst)
    group.addKnob(publishFirst)
    group.addKnob(renderLast)
    group.addKnob(publishLast)
    group.addKnob(usePublishRange)

    submit_to_deadline = nuke.PyScript_Knob(
        "submit", 
        "Submit to Deadline", 
        "update_ovs_write_version(nuke.thisNode());deadlineNetworkSubmit()"
    )

    clear_temp_outputs_button = nuke.PyScript_Knob(
        "clear",
        "Clear Temp Outputs",
        "import os;fpath = os.path.dirname(nuke.thisNode().knob('File output').value());[os.remove(os.path.join(fpath, f)) for f in os.listdir(fpath) if os.path.isfile(os.path.join(fpath, f))]",
    )
    publish_button = nuke.PyScript_Knob(
        "publish",
        "Publish",
        "check_and_show_publisher()",
        # "from ayon_core.tools.utils import host_tools;host_tools.show_publisher(tab='Publish')",
    )
    readfrom_src = "import read_node_utils;read_node_utils.write_to_read(nuke.thisNode(), allow_relative=False)"
    readfrom = nuke.PyScript_Knob(
        "readfrom", "Read From Rendered", readfrom_src
    )

    render_local_button = nuke.PyScript_Knob(
        "renderlocal",
        "Render Local",
        "import ayon_nuke.api.lib as lib;update_ovs_write_version(nuke.thisNode());nuke.toNode(f'inside_{nuke.thisNode().name()}').knob('Render').execute();save_script_with_render(nuke.thisNode()['File output'].getValue(),lib.get_node_data(nuke.thisNode(),'publish_instance')['is_ovs'])",
    )

    div = nuke.Text_Knob("div", "", "")
    deadlinediv = nuke.Text_Knob("deadlinediv", "Deadline", "")
    deadlinePriority = nuke.Int_Knob("deadlinePriority", "Priority")
    deadlineChunkSize = nuke.Int_Knob("deadlineChunkSize", "    Chunk Size")
    concurrentTasks = nuke.Int_Knob("concurrentTasks", "    Concurrent Tasks")
    deadlinePool = nuke.String_Knob("deadlinePool", "Pool")
    deadlineGroup = nuke.String_Knob("deadlineGroup", "Group")

    read_from_publish_button = nuke.PyScript_Knob(
        "readfrompublish",
        "Read From Publish",
        "read_node_utils.read_from_publish(nuke.thisNode())",
    )

    navigate_to_render_button = nuke.PyScript_Knob(
        "navigate_to_render",
        "Navigate to Render",
        "read_node_utils.navigate_to_render(nuke.thisNode())",
    )

    navigate_to_publish_button = nuke.PyScript_Knob(
        "navigate_to_publish",
        "Navigate to Publish",
        "read_node_utils.navigate_to_publish(nuke.thisNode())",
    )

    tempwarn = nuke.Text_Knob(
        "tempwarn",
        "",
        "- all rendered files are TEMPORARY and WILL BE OVERWRITTEN unless published ",
    )

    ovswarn = nuke.Text_Knob(
        "ovswarn",
        "",
        "- This node is for writing where the pipeline steps needs to be bypassed due to an incredibly long or large render.",
    )

    concurrent_warning = nuke.Text_Knob(
        "concurrent_warning", "", "<-- Set to 1 for heavy scripts"
    )

    deadlineChunkSize.setValue(1)
    concurrentTasks.setValue(2)
    deadlinePool.setValue("local")
    deadlineGroup.setValue("nuke")
    deadlinePriority.setValue(90)

    usePublishRange.setFlag(nuke.STARTLINE)
    submit_to_deadline.setFlag(nuke.STARTLINE)
    publishFirst.clearFlag(nuke.STARTLINE)
    publishLast.clearFlag(nuke.STARTLINE)
    render_local_button.setFlag(nuke.STARTLINE)
    deadlinePriority.setFlag(nuke.STARTLINE)
    deadlineChunkSize.clearFlag(nuke.STARTLINE)  # Don't start a new line
    #    concurrentTasks.clearFlag(nuke.STARTLINE)
    concurrent_warning.clearFlag(nuke.STARTLINE)

    group.addKnob(render_local_button)

    if not is_ovs:
        group.addKnob(readfrom)
        group.addKnob(clear_temp_outputs_button)
        group.addKnob(navigate_to_render_button)

    group.addKnob(deadlinediv)
    group.addKnob(deadlinePriority)
    group.addKnob(deadlineChunkSize)
    group.addKnob(concurrentTasks)
    group.addKnob(concurrent_warning)
    group.addKnob(deadlinePool)
    group.addKnob(deadlineGroup)
    group.addKnob(submit_to_deadline)
    group.addKnob(div)
    group.addKnob(publish_button)
    group.addKnob(read_from_publish_button)
    group.addKnob(navigate_to_publish_button)

    if is_ovs is False:
        group.addKnob(tempwarn)

    else:
        group.addKnob(ovswarn)

    endGroup = nuke.Tab_Knob("endpipeline", None, nuke.TABENDGROUP)

    group.addKnob(endGroup)


def show_quick_publish_info():
    """
    Show a simple info window with text content.
    """
    # Your info text - customize this as needed
    info_text = """
Quick Publish

Experimental alternative to the ayon ui for submitting publishes.

If "Transfer renders using farm" is unchecked, the transfers will take place locally and will freeze Nuke until complete. If the transfer is large, this could take a while, but nuke has probably not crashed.

If "Transfer renders using farm" is checked, the transfer will take place remotely.

"Generate review media" will create quicktimes and pngs according to a template nuke script and can be performed locally or remotely, but will be forced to process remotely if the transfer is remote.
    
    """

    nuke.message(info_text)


def embed_experimental():

    """
    Creates an experimental tab with additional publish options and quick publish functionality.
    """
    nde = nuke.thisNode()
    knb = nuke.thisKnob()

    # Only run when file_type knob changes, to avoid multiple calls
    if knb != nde.knob("file_type"):
        return

    # div = nuke.Text_Knob("div", "", "")
    # Get the parent group node
    group = nuke.toNode(".".join(["root"] + nde.fullName().split(".")[:-1]))

    # Check if experimental tab already exists
    if "experimental" in group.knobs():
        return

    # Create the Experimental tab (simple tab, not a group)
    experimental_tab = nuke.Tab_Knob(
        "experimental",
        "Quick Publish - experimental",
        nuke.TABBEGINCLOSEDGROUP,
    )

    # Check if this is a prerender node to skip review options
    is_prerender = False
    try:
        data = json.loads(
            group.knobs()["publish_instance"].value().replace("JSON:::", "", 1)
        )
        product_type = data.get("productType", "")
        is_prerender = product_type == "prerender"
    except (KeyError, TypeError, ValueError):
        is_prerender = False

    # Create checkboxes
    publish_on_farm_checkbox = nuke.Boolean_Knob(
        "publish_on_farm", "Transfer renders using Farm"
    )
    publish_on_farm_checkbox.setValue(False)
    publish_on_farm_checkbox.setTooltip(
        "Renders will be transferred to the publish location using the farm, unchecked will perform a local transfer"
    )
    publish_on_farm_checkbox.setFlag(nuke.STARTLINE)

    # Only create review related for non prerender nodes
    if not is_prerender:
        generate_review_checkbox = nuke.Boolean_Knob(
            "generate_review_media", "Generate Review Media"
        )
        generate_review_checkbox.setValue(True)
        generate_review_checkbox.setTooltip(
            "Generate review media (mp4/mov) for the rendered sequence based on the template nuke script"
        )
        generate_review_checkbox.setFlag(nuke.STARTLINE)

        generate_review_farm_checkbox = nuke.Boolean_Knob(
            "generate_review_media_on_farm", "Use farm for review media"
        )
        generate_review_farm_checkbox.setValue(False)
        generate_review_farm_checkbox.setTooltip(
            "Generate review media using the farm instead of locally"
        )
        generate_review_farm_checkbox.setFlag(nuke.STARTLINE)

        # If publish_on_farm is True, automatically set this to True and disable it
        if publish_on_farm_checkbox.value():
            generate_review_farm_checkbox.setValue(True)
            generate_review_farm_checkbox.setEnabled(False)

        burnin_checkbox = nuke.Boolean_Knob(
            "burnin", "Apply burnin to review proxy"
        )
        burnin_checkbox.setValue(True)
        burnin_checkbox.setTooltip(
            "Add burnin information (timecode, frame numbers, etc.) to proxy review media. Prores will not get burnin"
        )
        burnin_checkbox.setFlag(nuke.STARTLINE)

    quick_publish_button = nuke.PyScript_Knob(
        "quick_publish",
        "Quick Publish",
        "quick_publish_wrapper(nuke.thisNode())",
    )
    quick_publish_button.setTooltip("Submit publish")

    # Add the new text window button
    show_info_button = nuke.PyScript_Knob(
        "show_info",
        "Show Info",
        "quick_write.show_quick_publish_info()",
    )
    show_info_button.setTooltip("Display information window")

    # group.addKnob(div)
    spacer = nuke.Text_Knob("exp_spacer", "", "")
    group.addKnob(spacer)
    group.addKnob(experimental_tab)

    group.addKnob(publish_on_farm_checkbox)

    # Only add review related knobs for non prerender nodes
    if not is_prerender:
        group.addKnob(generate_review_checkbox)
        group.addKnob(generate_review_farm_checkbox)
        group.addKnob(burnin_checkbox)

    spacer = nuke.Text_Knob("exp_spacer", "", "")
    group.addKnob(spacer)
    group.addKnob(quick_publish_button)
    group.addKnob(show_info_button)


def handle_farm_publish_logic():
    """
    Handle the logic for farm publishing checkboxes.
    If publish_on_farm is checked, force generate_review_media_on_farm to True and disable it.
    """
    nde = nuke.thisNode()
    kb = nuke.thisKnob()

    if not kb or kb.name() != "publish_on_farm":
        return

    if not nde.knob("generate_review_media_on_farm"):
        return

    if kb.value():
        nde.knob("generate_review_media_on_farm").setValue(True)
        nde.knob("generate_review_media_on_farm").setEnabled(False)
    else:
        nde.knob("generate_review_media_on_farm").setEnabled(True)


def update_ovs_write_version(node):
    """
    Set the version of ovs quickwrite filepaths based on latest target version.
    This runs on Render Local and Submit to Deadline buttons.

    Args:
        node (nuke.Node): The OVS write node to update.
        This node should have the INSTANCE_DATA_KNOB containing the necessary data.
    """

    if INSTANCE_DATA_KNOB in node.knobs():
        data = json.loads(
            node.knobs()[INSTANCE_DATA_KNOB].value().replace("JSON:::", "", 1)
        )
        if "is_ovs" not in data.keys():
            log.warning(
                f"{node.name()} is missing is_ovs key, it is probably an old node"
            )
        else:
            if data["is_ovs"]:

                prompt = nuke.ask("Set render output path to latest new product version?")
                if prompt:
                    try:
                        fpath_new = get_ovs_pathing(data)
                        node_name = node["name"].value()
                        interior_write = "inside_" + node_name
                        wnode = nuke.toNode(interior_write)
                        if wnode is not None:
                            wnode["file"].setValue(fpath_new)
                            node["File output"].setValue(fpath_new)
                            log.info(f"Updating ovs write path for {node_name}: {fpath_new}")
                            nuke.toNode(node_name)
                        else:
                            log.warning(
                                f"Interior write node {interior_write} not found, cannot set file path."
                            )
                    except Exception as e:
                        log.error(f"Error setting ovs write version: {e}")
                        nuke.message(
                            "Error setting ovs write version. Check the console for details."
                        )
                else:
                    log.warning(
                        f"{node.name()} is potentially set to output to an old version, this may overwrite existing files on disk"
                    )
    else:
        log.debug(f"{node.name()} is missing instance data knob, cannot set version")



def get_all_ayon_write_nodes():
    ayon_write_nodes = []

    for node in nuke.allNodes():
        if node.Class() == "Group":
            # Check if it has AYON instance data
            if INSTANCE_DATA_KNOB in node.knobs():
                ayon_write_nodes.append(node)

    return ayon_write_nodes


def parse_publish_instance(qnode):
    return json.loads(qnode.knob(api.INSTANCE_DATA_KNOB).value()[7:])


def quick_publish_wrapper(node):
    from hornet_publish_utils import quick_publish

    # review = node["generate_review_media"].value()
    # review_farm = node["generate_review_media_on_farm"].value()
    # integrate_farm = node["publish_on_farm"].value()
    # burnin = node["burnin"].value()

    review_knob = node.knobs().get("generate_review_media")
    review = review_knob.value() if review_knob else False

    review_farm_knob = node.knobs().get("generate_review_media_on_farm")
    review_farm = review_farm_knob.value() if review_farm_knob else False

    integrate_farm_knob = node.knobs().get("publish_on_farm")
    integrate_farm = (
        integrate_farm_knob.value() if integrate_farm_knob else False
    )

    burnin_knob = node.knobs().get("burnin")
    burnin = burnin_knob.value() if burnin_knob else False

    with nuke.root():
        quick_publish(
            node,
            review=review,
            review_farm=review_farm,
            integrate_farm=integrate_farm,
            burnin=burnin,
        )
