import nuke
import os
from ayon_nuke import api
import json

from ayon_nuke.api.lib import (
    create_write_node,
)

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