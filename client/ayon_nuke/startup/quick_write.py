import nuke
import os
from ayon_nuke import api
import json
from ayon_core.lib import Logger


from ayon_nuke.api.lib import (
    create_write_node,
)

log = Logger.get_logger(__name__)

knobMatrix = {
    "exr": ["autocrop", "datatype", "heroview", "metadata", "interleave"],
    "png": ["datatype"],
    "dpx": ["datatype"],
    "tiff": ["datatype", "compression"],
    "jpeg": [],
}

def quick_write_node(family="render"):
    variant = nuke.getInput("Variant for Quick Write Node", "Main").title()
    _quick_write_node(variant, family, inpanel = True)

def _quick_write_node(variant, family="render", inpanel = True):

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
    print(folder_path)
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
    }

    print("inpanelVal2:", inpanel)

    qnode = create_write_node(
        family + os.environ["AYON_TASK_NAME"] + variant,
        data,
        prerender=True if family == "prerender" else False,
        inpanel = inpanel
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

#dict mapping extension to list of exposed parameters from write node to top level group node
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
            if knb.name() != api.INSTANCE_DATA_KNOB:
                group.removeKnob(knb)
        except:
            continue
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
        "submit", "Submit to Deadline", "deadlineNetworkSubmit()"
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
        "nuke.toNode(f'inside_{nuke.thisNode().name()}').knob('Render').execute();save_script_with_render(nuke.thisNode()['File output'].getValue())",
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
    group.addKnob(tempwarn)

    endGroup = nuke.Tab_Knob("endpipeline", None, nuke.TABENDGROUP)

    group.addKnob(endGroup)