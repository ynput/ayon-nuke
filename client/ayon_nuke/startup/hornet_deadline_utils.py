import json
import os
import getpass
import nuke
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from ayon_core.settings import get_current_project_settings  # type: ignore
    from ayon_api import get_bundle_settings  # type: ignore
except ImportError:
    print("oh well")


## copied from submit_nuke_to_deadline.py
def GetDeadlineCommand():
    # type: () -> str
    deadlineBin = ""  # type: str
    try:
        deadlineBin = os.environ["DEADLINE_PATH"]
    except KeyError:
        # if the error is a key error it means that DEADLINE_PATH is not set. however Deadline command may be in the PATH or on OSX it could be in the file /Users/Shared/Thinkbox/DEADLINE_PATH
        pass

    # On OSX, we look for the DEADLINE_PATH file if the environment variable does not exist.
    if deadlineBin == "" and os.path.exists(
        "/Users/Shared/Thinkbox/DEADLINE_PATH"
    ):
        with open("/Users/Shared/Thinkbox/DEADLINE_PATH") as f:
            deadlineBin = f.read().strip()

    deadlineCommand = os.path.join(deadlineBin, "deadlinecommand")  # type: str

    return deadlineCommand


def CallDeadlineCommand(arguments, hideWindow=True):
    deadlineCommand = GetDeadlineCommand()  # type: str

    startupinfo = None  # type: ignore # this is only a windows option
    if hideWindow and os.name == "nt":
        # Python 2.6 has subprocess.STARTF_USESHOWWINDOW, and Python 2.7 has subprocess._subprocess.STARTF_USESHOWWINDOW, so check for both.
        try:
            if hasattr(subprocess, "_subprocess") and hasattr(
                subprocess._subprocess,
                "STARTF_USESHOWWINDOW",  # type: ignore
            ):
                startupinfo = subprocess.STARTUPINFO()  # type: ignore # this is only a windows option
                startupinfo.dwFlags |= (
                    subprocess._subprocess.STARTF_USESHOWWINDOW
                )  # type: ignore # this is only a windows option
            elif hasattr(subprocess, "STARTF_USESHOWWINDOW"):
                startupinfo = subprocess.STARTUPINFO()  # type: ignore # this is only a windows option
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore # this is only a windows option
        except AttributeError:
            # Handle cases where subprocess attributes don't exist
            pass

    environment = {}
    for key in os.environ.keys():
        environment[key] = str(os.environ[key])

    if os.name == "nt":
        deadlineCommandDir = os.path.dirname(deadlineCommand)
        if not deadlineCommandDir == "":
            environment["PATH"] = (
                deadlineCommandDir + os.pathsep + os.environ["PATH"]
            )

    arguments.insert(0, deadlineCommand)
    output = ""

    # Specifying PIPE for all handles to workaround a Python bug on Windows. The unused handles are then closed immediatley afterwards.
    proc = subprocess.Popen(
        arguments,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        env=environment,
    )
    output, errors = proc.communicate()

    if sys.version_info[0] > 2 and type(output) is bytes:
        output = output.decode()

    return output  # type: ignore


## END copied from submit_nuke_to_deadline.py


def getSubmitterInfo():
    try:
        return json.loads(
            CallDeadlineCommand(
                [
                    "-prettyJSON",
                    "-GetSubmissionInfo",
                    "Pools",
                    "Groups",
                    "MaxPriority",
                    "UserHomeDir",
                    "RepoDir:submission/Nuke/Main",
                    "RepoDir:submission/Integration/Main",
                ]
            )
        )  # type: Dict

    except Exception as e:
        print("Failed to get submitter info: {}".format(e))


def getNodeSubmissionInfo(node):
    print("getNodeSubmissionInfo")
    # node = nuke.thisNode()
    if node is None:
        raise Exception("Node provided to getNodeSubmissionInfo None")
    if node.Class() != "Group":
        raise Exception(
            "Node provided to getNodeSubmissionInfo is not a Group"
        )
    # print(f"render node: {node.Class()}")
    # inside_name = node.parent().fullName() + "." + node.name() + ".inside_" + node.name()
    inside_name = node.fullName() + ".inside_" + node.name()
    inside_write = nuke.toNode(inside_name)

    if inside_write is None:
        raise Exception(
            f"Node provided to getNodeSubmissionInfo has no inside write node\nAttempted to get inside write node: {inside_name}"
        )

    relevant_knobs = [
        "File output",
        "deadlinePool",
        "deadlineGroup",
        "deadlinePriority",
        "deadlineChunkSize",
        "concurrentTasks",
    ]

    # relevant_inside_knobs = ["first", "last"]
    all_knobs = node.allKnobs()
    knob_values = {
        knb.name(): knb.value()
        for knb in all_knobs
        if knb.name() in relevant_knobs
    }

    try:
        first_knob = inside_write.knob("first")
        last_knob = inside_write.knob("last")
        if first_knob is not None:
            knob_values["first"] = first_knob.value()
        if last_knob is not None:
            knob_values["last"] = last_knob.value()
    except Exception as e:
        print(f"Failed to get first/last knobs from inside write node: {e}")

    return knob_values


def deadlineNetworkSubmit(*, dev=False, batch=None, silent=False, node=None):
    # TODO I added miliseconds to the timestamp which forms the file name to allow for batch submissions, otherwise it fails beacuse it tries to
    # overwrite the same file each time.
    # Would be better to save once per batch which requires refactor

    print("deadlineNetworkSubmit dev mode v4")

    if node is None:
        node = nuke.thisNode()

    if node is None:
        raise Exception("Node provided to submitter None")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    temp_script_path = "{path}/submission/{name}_{time}.nk".format(
        path=os.environ["AYON_WORKDIR"],
        name=os.path.splitext(os.path.basename(nuke.root().name()))[0],
        time=timestamp,
    )

    body = build_request(getNodeSubmissionInfo(node), temp_script_path, node)

    if batch is not None:
        body["JobInfo"]["BatchName"] = batch

    if dev:
        nuke.tprint(body)
        print(body)
        return

    file_path = body["PluginInfo"]["OutputFilePath"]
    nuke.tprint(f"File path: {file_path}")

    # save a copy of the script with the render as an artist discoverable backup
    save_script_with_render(
        Path(file_path)
    )  # ticket HPIPE-702 back up script with render

    # Create nuke script that render node will access
    if not os.path.exists(
        os.path.join(os.environ["AYON_WORKDIR"], "submission")
    ):
        os.mkdir(os.path.join(os.environ["AYON_WORKDIR"], "submission"))
    print(f"temp_script_path: {temp_script_path}")
    nuke.scriptSaveToTemp(temp_script_path)

    deadline_url = get_deadline_url()

    try:
        import requests
    except ImportError:
        raise Exception("failed to import requests")

    response = requests.post(deadline_url, json=body, timeout=10)

    if not response.ok:
        nuke.alert("Failed to submit to Deadline: {}".format(response.text))
        raise Exception(response.text)
    else:
        if not silent:
            nuke.alert("Submitted to Deadline Sucessfully")
        return True


def build_request(knobValues, temp_script_path, node):
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
    body = {
        "JobInfo": {
            # Job name, as seen in Monitor
            "Name": os.environ["AYON_PROJECT_NAME"].split("_")[0]
            + "_"
            + os.environ["AYON_FOLDER_PATH"]
            + "_"
            # + nuke.thisNode().fullName(),
            + node.fullName(),
            # pass submitter user
            "UserName": getpass.getuser(),
            "Priority": int(knobValues.get("deadlinePriority")) or 95,
            "Pool": knobValues.get("deadlinePool") or "local",
            "SecondaryPool": "",
            "Group": knobValues.get("deadlineGroup") or "nuke",
            "Plugin": "Nuke",
            "Frames": "{start}-{end}".format(
                start=int(knobValues["first"]) or nuke.root().firstFrame(),
                end=int(knobValues["last"]) or nuke.root().lastFrame(),
            ),
            # Optional, enable double-click to preview rendered
            # frames from Deadline Monitor
            # "OutputFilename0": str(output_filename_0).replace("\\", "/"),
            # limiting groups
            "ChunkSize": int(knobValues.get("deadlineChunkSize", 1)) or 1,
            "LimitGroups": "nuke-limit",
            "ConcurrentTasks": int(knobValues.get("concurrentTasks", 1)),
        },
        "PluginInfo": {
            # Input
            "SceneFile": temp_script_path.replace("\\", "/"),
            # Output directory and filename
            "OutputFilePath": knobValues["File output"].replace("\\", "/"),
            # "OutputFilePrefix": render_variables["filename_prefix"],
            # Mandatory for Deadline
            "Version": str(nuke.NUKE_VERSION_MAJOR)
            + "."
            + str(nuke.NUKE_VERSION_MINOR),
            # Resolve relative references
            "ProjectPath": nuke.script_directory().replace("\\", "/"),
            # using GPU by default
            # Only the specific write node is rendered.
            # "WriteNode": nuke.thisNode().fullName(),
            "WriteNode": node.fullName(),
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
    print(body)
    return body


def save_script_with_render(write_node_file_path, is_ovs=False):
    """
    Back up the script next to the render files

    Args:
        write_node_file_path (Path): the value of the "File" knob of the write node
        is_ovs (bool): whether the write node is an OVS write node
    """
    if is_ovs:
        nuke.tprint("Render is OVS: Skipping script save with local render.")
        return

    if not isinstance(write_node_file_path, Path):
        write_node_file_path = Path(write_node_file_path)

    scripts_subfolder = "scripts"

    nuke.tprint("write_node_file_path", str(write_node_file_path))

    # write_node_file_path.parent.mkdir(parents=True, exist_ok=True)
    script_name = Path(nuke.root().name()).stem
    render_dir = Path(write_node_file_path).parent
    render_name = str(Path(write_node_file_path.name)).split(".")[0]
    save_name = script_name + "__" + render_name + ".nk"
    save_path = render_dir / Path(scripts_subfolder) / save_name
    save_path.parent.mkdir(parents=True, exist_ok=True)
    nuke.tprint("save_path", str(save_path))

    if Path(save_path).exists():
        os.remove(save_path)

    # Save a copy next to render
    nuke.scriptSaveToTemp(str(save_path))
    if Path(save_path).exists():
        nuke.tprint("Saved script to {}".format(save_path))
    else:
        nuke.tprint("Failed to save script to {}".format(save_path))


def get_deadline_server():
    project_settings = get_current_project_settings()
    deadline_settings = project_settings["deadline"]

    deadline_server = deadline_settings["deadline_urls"][0]["value"]
    if not deadline_server or deadline_server in [
        "http://127.0.0.1:8082",
        "http://localhost:8082",
    ]:
        # If it is, fetch the settings from the production bundle
        bundle_settings = get_bundle_settings(variant="production")["addons"]
        deadline_settings = next(
            (
                addon
                for addon in bundle_settings
                if addon.get("name") == "deadline"
            ),
            None,
        )

        if deadline_settings:
            deadline_server = deadline_settings["settings"]["deadline_urls"][
                0
            ]["value"]
    print(f"Current Deadline Webserver URL: {deadline_server}")

    return deadline_server


def get_deadline_url():
    deadline_server = get_deadline_server()
    deadline_url = "{}/api/jobs".format(deadline_server)
    return deadline_url
