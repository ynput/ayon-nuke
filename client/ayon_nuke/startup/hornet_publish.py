import os
import getpass
from re import L
import shutil
import nuke
import json
# import hornet_deadline_utils
# import requests
from hornet_deadline_utils import get_deadline_url
from pathlib import Path
from datetime import datetime
from file_sequence import SequenceFactory
from pathlib import Path

try:
    from ayon_core.settings import get_current_project_settings  # type: ignore
    from ayon_api import get_bundle_settings  # type: ignore
    import requests
except ImportError:
    print("failed to import ayon_core or ayon_api. this might not be a problem.")




# TEMPLATE_SCRIPT = "P:/dev/alexh_dev/hornet_publish/hornet_publish_template.nk"


def hornet_publish_configurate(data = None):

    print("hornet_publish_configurate")

    debug_log = ""

    if data is None:
        d = os.environ.get("HORNET_PUBLISH", None)
        if d is None:
            raise Exception("HORNET_PUBLISH is not set")
        data = json.loads(d)
    
    debug_log += f"data: {data}\n"

    read_node = nuke.toNode("PublishRead")
    data_node = nuke.toNode("Data")
    data_node["shot_name"].setValue(data["shot"])
    data_node["render_name"].setValue(data["name"])
    data_node["project_name"].setValue(data["project"])



    if read_node is None:
        raise Exception("failed to get read node")
    
    fs = SequenceFactory.from_sequence_string_absolute(Path(data["publishedSequence"]))
    
    if not fs:
        raise Exception("failed to create file sequence")


    read_node = nuke.toNode("PublishRead")
    string = f"{fs.absolute_file_name} {fs.first_frame}-{fs.last_frame}"
    read_node["file"].fromUserText(string)

    print(f"read node path: {read_node['file'].getValue()}")
    debug_log += f"read node path: {read_node['file'].getValue()}\n"

    write_nodes = nuke.allNodes("Write")

    for write in write_nodes:
        configure_write_node(write, data)

    sticky = nuke.nodes.StickyNote()
    sticky["name"].setValue("debug log")
    sticky['label'].setValue(debug_log)

    script_path = Path(nuke.toNode("root").name())
    log_file_name = (script_path.parent / script_path.stem).with_suffix(".log")
    with open(log_file_name, "w") as f:
        f.write(debug_log)

    nuke.scriptSave()
    print(f"debug log: {debug_log}")
    print(f"log file: {log_file_name}")


def discover_write_nodes_in_script(script_path):
    # Save current node selection state
    current_nodes = set(nuke.allNodes())
    new_nodes = set()
    
    try:
        # Import nodes from template into current script
        nuke.nodePaste(script_path)
        
        # Find newly imported nodes
        new_nodes = set(nuke.allNodes()) - current_nodes
        write_nodes = [n.name() for n in new_nodes if n.Class() == "Write"]
        
        return write_nodes
        
    finally:
        # Clean up: delete imported nodes
        for node in new_nodes:
            nuke.delete(node)

def configure_write_node(write, data):

    format = write['file_type'].value()
    publish_loc = Path(data["publishDir"]);
    publish_loc = publish_loc / "review"
    publish_loc.mkdir(parents=True, exist_ok=True)
    if not publish_loc.exists():
        raise Exception("failed to create publish location")
        

    new_path = f"{publish_loc.as_posix()}/{data['name']}_v{data['version']:0>3}_{write.name()}.{format}"
    print(f"new path: {new_path}")
    write['file'].setValue(new_path)

def hornet_review_media_submit(data, logger=None):
    print("hornet_publish_submit!!!")

    if logger:
        logger.info("hornet_review_media_submit log")


    env_vars = json.dumps(data)
    nd = nuke.toNode(data["writeNode"])
    fs = SequenceFactory.from_nuke_node(nd)
    if fs is None:
        raise Exception("failed to get file sequence")
    logger.info(f"file sequence: {fs}")

    first = fs.first_frame
    last = fs.last_frame

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    publish_temp_script_path = (
        "{path}/submission/publish/{name}_review_media_gen_{time}.nk".format(
            path=os.environ["AYON_WORKDIR"],
            name=os.path.splitext(os.path.basename(nuke.root().name()))[0],
            time=timestamp,
        )
    )
    print(f"pub_temp_script_path: {publish_temp_script_path}")

    """
    data is dumped into an env var because hornet_publish_configurate is called
    by the onScriptLoad callback, which means we cannot pass any arguments to it.
    """

    Path(publish_temp_script_path).parent.mkdir(parents=True, exist_ok=True)
    template_script = data.get("template_script", None)
    copy_template_to_temp(template_script, publish_temp_script_path)
    deadline_url = get_deadline_url()
    write_nodes = discover_write_nodes_in_script(publish_temp_script_path)

    logger.info(f"write_nodes: {write_nodes}")

    successful_submissions = 0
    failed_submissions = 0

    for node_name in write_nodes:

        # nd = nuke.toNode(node_name)
        # logger.info(f"nd: {nd}")
        # fl = nd['file'].getValue()

        submission_info = {
            # "file": fl,
            "task_name": f"{data['shot']}_{data['name']}_{node_name}_review",
            "deadlinePriority": 95,
            "deadlinePool": "local",
            "deadlineGroup": "nuke",
            "deadlineChunkSize": last - first + 1,
            "concurrentTasks": 1,
            "Frames": f"{first}-{last}",
            "write_node_name": f"{node_name}",
        }

        body = build_request(submission_info, publish_temp_script_path, env_vars)

        print(f"body: {body}")  

        response = requests.post(deadline_url, json=body, timeout=10)
    
        if not response.ok:
            # nuke.alert("Failed to submit to Deadline: {}".format(response.text))
            failed_submissions += 1
        else:
            # nuke.alert("Submitted to Deadline Sucessfully")
            successful_submissions += 1
    
    # nuke.alert(f"{successful_submissions} successful submissions, {failed_submissions} failed submissions")
    if logger:
        logger.info(f"successful_submissions: {successful_submissions}")
        logger.info(f"failed_submissions: {failed_submissions}")

    if successful_submissions > 0:
        return True
    else:
        return False

def build_request(submission_info, temp_script_path, publish_env_vars):
    # Include critical environment variables with submission
    print("build_request")
    submissionEnvVars = [
        "HORNET_ROOT",
        "NUKE_PATH",
        "OCIO",
        "OPTICAL_FLARES_PATH",
        "peregrinel_LICENSE",
        "OFX_PLUGIN_PATH",
        "RVL_SERVER",
        "neatlab_LICENSE",
    ]
    environment = dict(
        {k: os.environ[k] for k in submissionEnvVars if k in os.environ.keys()}
    )
    # environment["HARDING"] = "picard"
    environment["HORNET_PUBLISH"] = publish_env_vars
    body = {
        "JobInfo": {
            # Job name, as seen in Monitor
            "Name": os.environ["AYON_PROJECT_NAME"].split("_")[0]
            + "_"
            # + os.environ["AYON_FOLDER_PATH"]
            # + "_"
            + submission_info.get("task_name" or "task name error"),
            "UserName": getpass.getuser(),
            "Priority": int(submission_info.get("deadlinePriority")) or 95,
            "Pool": submission_info.get("deadlinePool") or "local",
            "SecondaryPool": "",
            "Group": submission_info.get("deadlineGroup") or "nuke",
            "Plugin": "Nuke",
            "Frames": submission_info.get("Frames"),
            "ChunkSize": int(submission_info.get("deadlineChunkSize", 1)) or 1,
            "LimitGroups": "nuke-limit",
            "ConcurrentTasks": int(submission_info.get("concurrentTasks", 1)),
        },
        "PluginInfo": {
            "SceneFile": temp_script_path.replace("\\", "/"),
            # Output directory and filename
            # "OutputFilePath": submission_info["file"].replace("\\", "/"),
            # "OutputFilePrefix": render_variables["filename_prefix"],
            # Mandatory for Deadline
            "Version": str(nuke.NUKE_VERSION_MAJOR)
            + "."
            + str(nuke.NUKE_VERSION_MINOR),
            # Resolve relative references
            "ProjectPath": nuke.script_directory().replace("\\", "/"),
            # using GPU by default
            # Only the specific write node is rendered.
            "WriteNode": submission_info.get("write_node_name"),
        },
        # Mandatory for Deadline, may be empty
        "AuxFiles": [],
    }
    body["JobInfo"].update(
        {
            "EnvironmentKeyValue%d" % index: "{key}={value}".format(
                key=key, value=str(environment[key])
            )
            for index, key in enumerate(environment)
        }
    )
    return body


def apply_fileseq_to_node(fs, node):
    if node.Class() != "Write":
        raise Exception(
            "Node provided to apply_fileseq_to_node is not a Write node"
        )

    node["file"].fromUserText(
        f"{fs.absolute_file_name} {fs.first_frame}-{fs.last_frame}"
    )

def copy_template_to_temp(template_path, temp_script_path):
    print(f"copy_template_to_temp: {template_path} to {temp_script_path}")
    shutil.copy(template_path, temp_script_path)