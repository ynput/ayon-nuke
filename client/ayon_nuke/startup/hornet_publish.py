import os
import getpass
import shutil
import nuke
import json
from hornet_deadline_utils import get_deadline_url
from pathlib import Path
from datetime import datetime
from file_sequence import SequenceFactory

try:
    from ayon_core.settings import get_current_project_settings  # type: ignore
    from ayon_api import get_bundle_settings  # type: ignore
    import requests
except ImportError:
    print("failed to import ayon_core or ayon_api. this is probably fine.")


COLORSPACE_LOOKUP = {
    "Output - Rec.709": "rec709",
    "Output - sRGB": "sRGB",
    "Output - Rec.2020": "rec2020",
    "ACES - ACEScg": "ACEScg",
    "color_picking": "sRGB",
}


def validate_template_script(template_script, logger=None):
    log = MiniLogger(logger)

    log.info(f"validating template script: {template_script}")

    if template_script is None:
        raise Exception(
            "template_script is None\n have you entered the correct path to the template script in the Ayon web ui?\n The setting can be found under Nuke publish plugins"
        )

    if not os.path.isfile(template_script):
        raise Exception(
            "template_script is not a file\n have you entered the correct path to the template script in the Ayon web ui?\n The setting can be found under Nuke publish plugins"
        )

    if os.path.splitext(template_script)[1] != ".nk":
        raise Exception(
            "template_script is not a .nk file\n have you entered the correct path to the template script in the Ayon web ui?\n The setting can be found under Nuke publish plugins"
        )

    return True


def resolve_submission_script(data, write_node_name, logger=None):
    log = MiniLogger(logger)

    template_script = data["template_script"]

    log.info(f"resolving submission script from: {template_script}")

    # write_node = nuke.toNode(write_node_name)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    script_name = os.path.splitext(os.path.basename(nuke.root().name()))[0]
    submitter_node_name = data.get("name", "__submitter_node_name_unknown__")
    representations_name = write_node_name
    # colorspace = get_colorspace_name(write_node["colorspace"].value())
    name = script_name + "_" + submitter_node_name + "_" + representations_name

    submission_script = (
        "{path}/submission/publish/{name}_review_media_gen_{time}.nk".format(
            path=os.environ["AYON_WORKDIR"],
            name=name,
            time=timestamp,
        )
    )

    log.debug(f"submission script: {submission_script}")

    try:
        Path(submission_script).parent.mkdir(parents=True, exist_ok=True)
        copy_template_to_temp(template_script, submission_script)
    except Exception as e:
        raise Exception(f"failed to create publish temp script path: {e}")

    return submission_script


# TEMPLATE_SCRIPT = "P:/dev/alexh_dev/hornet_publish/hornet_publish_template.nk"
def hornet_review_media_submit(data, logger=None):
    log = MiniLogger(logger)

    env_vars = json.dumps(data)
    nd = nuke.toNode(data["writeNode"])

    fs = SequenceFactory.from_nuke_node(nd)
    if fs is None:
        raise Exception("failed to get file sequence")

    log.debug(f"file sequence: {fs}")

    global_first = fs.first_frame
    global_last = fs.last_frame

    # This will raise an exception if validation fails
    validate_template_script(data.get("template_script", None), logger)

    """
    data is dumped into an env var because hornet_publish_configurate is called
    by the onScriptLoad callback, which means we cannot pass any arguments to it.
    """
    write_node_info = discover_write_nodes_in_script(data["template_script"])

    log.debug(f"write_nodes: {write_node_info}")

    deadline_url = get_deadline_url()
    successful_submissions = 0
    failed_submissions = 0

    for node_info in write_node_info:
        # Create a separate submission script for each write node
        node_name = node_info[0]
        first = node_info[1]
        last = node_info[2]
        submission_script = resolve_submission_script(
            data,
            write_node_name=node_name,
            logger=logger,
        )

        submission_info = {
            "task_name": f"{data['shot']}_{data['name']}_{node_name}_review",
            "deadlinePriority": 95,
            "deadlinePool": "local",
            "deadlineGroup": "nuke",
            "deadlineChunkSize": last
            - first
            + 1,  # Render entire sequence in one chunk for review media
            "concurrentTasks": 1,
            "Frames": f"{first}-{last}",  # Let Deadline determine frame range from node metadata
            "write_node_name": f"{node_name}",
        }

        body = build_request(submission_info, submission_script, env_vars)
        log.debug(f"body for {node_name}: {body}")
        print(f"body: {body}")

        if "requests" not in globals():
            raise Exception(
                "requests module not available - needed for deadline submission"
            )

        response = requests.post(deadline_url, json=body, timeout=10)

        if not response.ok:
            failed_submissions += 1
        else:
            successful_submissions += 1

    log.debug(f"successful_submissions: {successful_submissions}")
    log.debug(f"failed_submissions: {failed_submissions}")

    # Return True if we had any successful submissions, False otherwise
    return successful_submissions > 0


def hornet_publish_configurate(data=None):
    print("hornet_publish_configurate")

    log = MiniLogger(None)

    # Start building comprehensive debug log
    debug_log = "=== HORNET PUBLISH CONFIGURATE DEBUG LOG ===\n"
    debug_log += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    debug_log += f"Function called at: {datetime.now().isoformat()}\n\n"

    if data is None:
        d = os.environ.get("HORNET_PUBLISH", None)
        if d is None:
            debug_log += (
                "ERROR: HORNET_PUBLISH environment variable is not set\n"
            )
            raise Exception("HORNET_PUBLISH is not set")
        data = json.loads(d)
        debug_log += "Data loaded from HORNET_PUBLISH environment variable\n"
    else:
        debug_log += "Data provided directly as parameter\n"

    debug_log += "\n=== INPUT DATA ===\n"
    for key, value in data.items():
        debug_log += f"{key}: {value}\n"

    debug_log += "\n=== ENVIRONMENT VARIABLES ===\n"
    relevant_env_vars = [
        "AYON_WORKDIR",
        "AYON_PROJECT_NAME",
        "AYON_FOLDER_PATH",
        "NUKE_PATH",
        "OCIO",
    ]
    for env_var in relevant_env_vars:
        debug_log += f"{env_var}: {os.environ.get(env_var, 'NOT SET')}\n"

    try:
        read_node = GetReadNode()
        debug_log += "\n=== READ NODE CONFIGURATION ===\n"
        debug_log += f"Read node found: {read_node.name()}\n"
    except Exception as e:
        debug_log += "\n=== READ NODE ERROR ===\n"
        debug_log += f"Failed to get read node: {str(e)}\n"
        read_node = None

    # Get file sequence information
    debug_log += "\n=== FILE SEQUENCE INFORMATION ===\n"
    try:
        fs = GetFileSequence(data)
        debug_log += "File sequence created successfully\n"
        debug_log += f"Absolute file name: {fs.absolute_file_name}\n"
        debug_log += f"First frame: {fs.first_frame}\n"
        debug_log += f"Last frame: {fs.last_frame}\n"
        debug_log += f"Frame count: {fs.last_frame - fs.first_frame + 1}\n"
        debug_log += f"Sequence string: {fs.sequence_string()}\n"
    except Exception as e:
        debug_log += f"ERROR: Failed to create file sequence: {str(e)}\n"
        raise Exception("failed to create file sequence")

    if read_node:
        try:
            string = (
                f"{fs.absolute_file_name} {fs.first_frame}-{fs.last_frame}"
            )
            read_node["file"].fromUserText(string)
            read_node["colorspace"].setValue(data.get("colorspace", None))
            debug_log += (
                f"Read node file path set to: {read_node['file'].getValue()}\n"
            )
            debug_log += f"Read node colorspace set to: {data.get('colorspace', 'None')}\n"
        except Exception as e:
            debug_log += f"ERROR: Failed to configure read node: {str(e)}\n"

    debug_log += "\n=== WRITE NODES CONFIGURATION ===\n"
    write_nodes = nuke.allNodes("Write")
    debug_log += f"Found {len(write_nodes)} write nodes\n"

    # Collect write node names for the log file
    write_node_names = []
    for i, write in enumerate(write_nodes):
        try:
            debug_log += f"\nWrite Node {i + 1}: {write.name()}\n"
            debug_log += f"  Original file path: {write['file'].getValue()}\n"
            debug_log += (
                f"  Original file type: {write['file_type'].value()}\n"
            )
            debug_log += (
                f"  Original colorspace: {write['colorspace'].value()}\n"
            )

            configure_write_node(write, data, log)
            write_node_names.append(write.name())

            debug_log += (
                f"  Configured file path: {write['file'].getValue()}\n"
            )
            debug_log += "  Configuration successful\n"
        except Exception as e:
            debug_log += f"  ERROR: Failed to configure write node {write.name()}: {str(e)}\n"

    debug_log += "\n=== DATA NODE POPULATION ===\n"
    try:
        populate_data_node(data)
        debug_log += "Data node populated successfully\n"
        debug_log += f"  Shot: {data.get('shot', 'N/A')}\n"
        debug_log += f"  Render name: {data.get('name', 'N/A')}\n"
        debug_log += f"  Project: {data.get('project', 'N/A')}\n"
        debug_log += f"  Version: {data.get('version', 'N/A')}\n"
    except Exception as e:
        debug_log += f"ERROR: Failed to populate data node: {str(e)}\n"

    debug_log += "\n=== SCRIPT INFORMATION ===\n"
    try:
        script_path = Path(nuke.toNode("root").name())
        debug_log += f"Script path: {script_path}\n"
        debug_log += f"Script directory: {script_path.parent}\n"
        debug_log += f"Script name: {script_path.name}\n"
    except Exception as e:
        debug_log += f"ERROR: Failed to get script information: {str(e)}\n"
        script_path = Path("unknown_script.nk")

    # Create sticky note with debug info
    try:
        sticky = nuke.nodes.StickyNote()
        sticky["name"].setValue("debug log")
        sticky["label"].setValue(debug_log)
        debug_log += "\nSticky note created with debug information\n"
    except Exception as e:
        debug_log += f"\nERROR: Failed to create sticky note: {str(e)}\n"

    # Include write node names in log file name
    if write_node_names:
        write_nodes_str = "_".join(write_node_names)
        log_file_name = (
            script_path.parent / f"{script_path.stem}_{write_nodes_str}"
        ).with_suffix(".log")
        debug_log += (
            f"Log file will include write node names: {write_nodes_str}\n"
        )
    else:
        log_file_name = (script_path.parent / script_path.stem).with_suffix(
            ".log"
        )
        debug_log += "No write nodes found for log file naming\n"

    debug_log += "\n=== FINAL STATUS ===\n"
    debug_log += f"Log file path: {log_file_name}\n"
    debug_log += f"Configuration completed at: {datetime.now().isoformat()}\n"
    debug_log += "=== END DEBUG LOG ===\n"

    for node in nuke.allNodes("Write"):
        debug_log += f"Write node: {node.name()}\n"
        debug_log += f"  first frame: {node.firstFrame()}\n"
        debug_log += f"  last frame: {node.lastFrame()}\n"

    try:
        with open(log_file_name, "w") as f:
            f.write(debug_log)
        debug_log += "Debug log written to file successfully\n"
    except Exception as e:
        debug_log += f"ERROR: Failed to write debug log to file: {str(e)}\n"

    try:
        nuke.scriptSave()
        debug_log += "Script saved successfully\n"
    except Exception as e:
        debug_log += f"ERROR: Failed to save script: {str(e)}\n"

    print(f"debug log: {debug_log}")
    print(f"log file: {log_file_name}")


def populate_data_node(data):
    data_node = nuke.toNode("Data")
    data_node["shot_name"].setValue(data["shot"])
    data_node["render_name"].setValue(data["name"])
    data_node["project_name"].setValue(data["project"])
    data_node["version"].setValue(data["version"])
    data_node["burnin"].setValue(data["burnin"])
    data_node["firstFrame"].setValue(data["first_frame"])
    data_node["lastFrame"].setValue(data["last_frame"])


def discover_write_nodes_in_script(script_path):
    # Save current node selection state
    current_nodes = set(nuke.allNodes())
    new_nodes = set()

    try:
        # Import nodes from template into current script
        nuke.nodePaste(script_path)

        # Find newly imported nodes
        new_nodes = set(nuke.allNodes()) - current_nodes
        # write_node_names = [
        #     n.name() for n in new_nodes if n.Class() == "Write"
        # ]
        write_node_info = []
        for node in new_nodes:
            if node.Class() == "Write" and node["disable"].getValue() == False:
                write_node_info.append(
                    (
                        node.name(),
                        node.firstFrame(),
                        node.lastFrame(),
                    )
                )

        return write_node_info

    finally:
        # Clean up: delete imported nodes
        for node in new_nodes:
            nuke.delete(node)


def configure_write_node(write, data, log):
    if type(write) == str:
        write = nuke.toNode(write)

    format = write["file_type"].value()
    publish_loc = Path(data["publishDir"])
    publish_loc = publish_loc / "review"
    publish_loc.mkdir(parents=True, exist_ok=True)
    if not publish_loc.exists():
        raise Exception("failed to create publish location")

    sanitized_colorspace_name = get_colorspace_name(
        write["colorspace"].value()
    )

    if "mov64_fps" in write.knobs():
        write["mov64_fps"].setValue(data["fps"])

        log.debug(f"fps set to: {write['mov64_fps'].getValue()}")

    new_path = f"{publish_loc.as_posix()}/{data['shot']}_{data['name']}_v{data['version']:0>3}_{write.name()}_{sanitized_colorspace_name}.{format}"
    print(f"new path: {new_path}")
    write["file"].setValue(new_path)


def build_request(submission_info, temp_script_path, publish_env_vars):
    # Include critical environment variables with submission
    # print("build_request")
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


def generate_review_media_local(data, logger=None):
    log = MiniLogger(logger)

    log.info("generate_review_media_local log")

    if data is None:
        raise Exception("data is None")

    log.debug(f"data: {data}")

    template_script = data.get("template_script", None)
    if template_script is None:
        raise Exception("template_script is None")

    for node in nuke.allNodes():
        node.setSelected(False)

    current_nodes = set(nuke.allNodes())
    new_nodes = set()
    nuke.nodePaste(template_script)
    new_nodes = set(nuke.allNodes()) - current_nodes
    backdrops = []
    for node in new_nodes:
        if node.Class() == "BackdropNode":
            nuke.delete(node)
            backdrops.append(node)
    for backdrop in backdrops:
        new_nodes.remove(backdrop)

    for node in new_nodes:
        node.setSelected(True)

    nuke.autoplace_all()

    write_nodes = [n.name() for n in new_nodes if n.Class() == "Write"]

    # Find read node among the newly pasted nodes instead of existing script
    read_nodes = [n for n in new_nodes if n.Class() == "Read"]
    if not read_nodes:
        # Fallback to looking for PublishRead in existing script
        try:
            read_node = GetReadNode()
        except Exception as e:
            log.warning(
                f"No read node found in template or existing script: {e}"
            )
            read_node = None
    else:
        # Use the first read node from the template
        read_node = read_nodes[0]
        log.debug(f"Found read node in template: {read_node.name()}")

    populate_data_node(
        data
    )  # TODO potential issue if there is some other node called data
    fs = GetFileSequence(data)

    # Apply file sequence to read node
    if read_node:
        try:
            string = (
                f"{fs.absolute_file_name} {fs.first_frame}-{fs.last_frame}"
            )
            read_node["file"].fromUserText(string)
            colorspace = data.get("colorspace", None)
            if colorspace:
                read_node["colorspace"].setValue(colorspace)
            log.debug(
                f"Read node file path set to: {read_node['file'].getValue()}"
            )
            log.debug(f"Read node colorspace set to: {colorspace}")
        except Exception as e:
            log.warning(f"Failed to configure read node: {e}")

    for node_name in write_nodes:
        configure_write_node(node_name, data, log)

    n = nuke.toNode(node_name)
    if n is None:
        raise Exception(f"failed to get write node: {node_name}")

    for node_name in write_nodes:
        nuke.execute(node_name, n.firstFrame(), n.lastFrame())

    for node_name in new_nodes:
        nuke.delete(node_name)

    return True


def GetReadNode():
    read_node = nuke.toNode("PublishRead")
    if read_node is None:
        raise Exception("failed to get read node")
    return read_node


def GetFileSequence(data):
    fs = SequenceFactory.from_sequence_string_absolute(
        Path(data["publishedSequence"])
    )
    if fs is None:
        raise Exception("failed to get file sequence")
    return fs


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
    try:
        shutil.copy(template_path, temp_script_path)
    except Exception as e:
        raise Exception(f"failed to copy template to temp: {e}")


def get_colorspace_name(colorspace):
    return COLORSPACE_LOOKUP.get(colorspace, colorspace.replace(" ", "_"))


class MiniLogger:
    """
    A simple logger wrapper that always prints and optionally logs to a real logger.
    Handles the case where no logger is provided gracefully.
    """

    def __init__(self, logger=None):
        self.logger = logger

    def log(self, message, level="info"):
        """
        Log a message - always prints, and logs to real logger if available.

        Args:
            message: The message to log/print
            level: Log level (info, debug, warning, error) - defaults to info
        """
        # Always print the message
        print(message)
        nuke.tprint(message)

        # If we have a real logger, use it too
        if self.logger:
            log_method = getattr(self.logger, level.lower(), self.logger.info)
            log_method(message)

    def info(self, message):
        """Log at info level"""
        self.log(message, "info")

    def debug(self, message):
        """Log at debug level"""
        self.log(message, "debug")

    def warning(self, message):
        """Log at warning level"""
        self.log(message, "warning")

    def error(self, message):
        """Log at error level"""
        self.log(message, "error")
