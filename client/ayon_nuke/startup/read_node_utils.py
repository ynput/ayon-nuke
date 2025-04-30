

import re
import os
import glob
import nuke
import json
import platform
from pathlib import Path
from ayon_core.lib import Logger
from file_sequence import FileSequence, Components

log = Logger.get_logger(__name__)

SINGLE_FILE_FORMATS = [
    "avi",
    "mp4",
    "mxf",
    "mov",
    "mpg",
    "mpeg",
    "wmv",
    "m4v",
    "m2v",
]


def evaluate_filepath_new(
    k_value, k_eval, project_dir, first_frame, allow_relative
):
    # get combined relative path
    combined_relative_path = None
    if k_eval is not None and project_dir is not None:
        combined_relative_path = os.path.abspath(
            os.path.join(project_dir, k_eval)
        )
        combined_relative_path = combined_relative_path.replace("\\", "/")
        filetype = combined_relative_path.split(".")[-1]
        frame_number = re.findall(r"\d+", combined_relative_path)[-1]
        basename = combined_relative_path[
            : combined_relative_path.rfind(frame_number)
        ]
        filepath_glob = basename + "*" + filetype
        glob_search_results = glob.glob(filepath_glob)
        if len(glob_search_results) <= 0:
            combined_relative_path = None

    try:
        # k_value = k_value % first_frame
        if os.path.isdir(os.path.basename(k_value)):
            # doesn't check for file, only parent dir
            filepath = k_value
        elif os.path.exists(k_eval):
            filepath = k_eval
        elif not isinstance(project_dir, type(None)) and not isinstance(
            combined_relative_path, type(None)
        ):
            filepath = combined_relative_path

        filepath = os.path.abspath(filepath)
    except Exception as E:
        log.error(
            "Cannot create Read node. Perhaps it needs to be \
                  rendered first :) Error: `{}`".format(E)
        )
        return None

    filepath = filepath.replace("\\", "/")
    # assumes last number is a sequence counter
    current_frame = re.findall(r"\d+", filepath)[-1]
    padding = len(current_frame)
    basename = filepath[: filepath.rfind(current_frame)]
    filetype = filepath.split(".")[-1]

    # sequence or not?
    if filetype in SINGLE_FILE_FORMATS:
        pass
    else:
        # Image sequence needs hashes
        # to do still with no number not handled
        filepath = basename + "#" * padding + "." + filetype

    # relative path? make it relative again
    if allow_relative:
        if (not isinstance(project_dir, type(None))) and project_dir != "":
            filepath = filepath.replace(project_dir, ".")

    # get first and last frame from disk
    frames = []
    firstframe = 0
    lastframe = 0
    filepath_glob = basename + "*" + filetype
    glob_search_results = glob.glob(filepath_glob)
    for f in glob_search_results:
        frame = re.findall(r"\d+", f)[-1]
        frames.append(frame)
    frames = sorted(frames)
    firstframe = frames[0]
    lastframe = frames[len(frames) - 1]

    if int(lastframe) < 0:
        lastframe = firstframe

    return filepath, firstframe, lastframe


def create_read_node(ndata, comp_start):
    nuke.tprint(ndata["filepath"])
    print(ndata["filepath"])

    read = nuke.createNode("Read", 'file "' + ndata["filepath"] + '"')
    read.knob("colorspace").setValue(int(ndata["colorspace"]))
    read.knob("raw").setValue(ndata["rawdata"])
    read.knob("first").setValue(int(ndata["firstframe"]))
    read.knob("last").setValue(int(ndata["lastframe"]))
    read.knob("origfirst").setValue(int(ndata["firstframe"]))
    read.knob("origlast").setValue(int(ndata["lastframe"]))
    if comp_start == int(ndata["firstframe"]):
        read.knob("frame_mode").setValue("1")
        read.knob("frame").setValue(str(comp_start))
    else:
        read.knob("frame_mode").setValue("0")
    read.knob("xpos").setValue(ndata["new_xpos"])
    read.knob("ypos").setValue(ndata["new_ypos"])
    nuke.inputs(read, 0)
    return


def write_to_read(write_group_node, allow_relative=False):
    comp_start = nuke.Root().knob("first_frame").value()
    project_dir = nuke.Root().knob("project_directory").getValue()
    if not os.path.exists(project_dir):
        project_dir = nuke.Root().knob("project_directory").evaluate()

    group_read_nodes = []
    with write_group_node:
        height = write_group_node.screenHeight()  # get group height and position
        new_xpos = int(write_group_node.knob("xpos").value())
        new_ypos = int(write_group_node.knob("ypos").value()) + height + 20
        group_writes = [n for n in nuke.allNodes() if n.Class() == "Write"]
        if group_writes != []:
            # there can be only 1 write node, taking first
            n = group_writes[0]

            if n.knob("file") is not None:

                result = evaluate_filepath_new(
                    n.knob("file").getValue(),
                    n.knob("file").evaluate(),
                    project_dir,
                    comp_start,
                    allow_relative,
                )

                if result is not None:
                    myfile, firstFrame, lastFrame = result
                else:
                    nuke.message("No render found")
                    return

                # myfile, firstFrame, lastFrame = evaluate_filepath_new(
                #     n.knob("file").getValue(),
                #     n.knob("file").evaluate(),
                #     project_dir,
                #     comp_start,
                #     allow_relative,
                # )
                # if not myfile:
                #     return

                # get node data
                ndata = {
                    "filepath": myfile,
                    "firstframe": int(firstFrame),
                    "lastframe": int(lastFrame),
                    "new_xpos": new_xpos,
                    "new_ypos": new_ypos,
                    "colorspace": n.knob("colorspace").getValue(),
                    "rawdata": n.knob("raw").value(),
                    "write_frame_mode": str(n.knob("frame_mode").value()),
                    "write_frame": n.knob("frame").value(),
                }
                group_read_nodes.append(ndata)

    # create reads in one go
    for oneread in group_read_nodes:
        # create read node
        create_read_node(oneread, comp_start)


def slice_path(path, start, end):
    # return a re-joined path from a slice of path parts

    path = Path(path)
    return Path(path.parts[start]).joinpath(*path.parts[start + 1 : end])


def get_publish_instance_data(write_node):
    # parse the json data from the write node

    return json.loads(
        write_node["publish_instance"].value().replace("JSON:::", "")
    )


def assemble_publish_path(ayon_write_node):
    from ayon_core.pipeline import registered_host, Anatomy

    host = registered_host()
    context = host.get_current_context()
    instance_data = get_publish_instance_data(ayon_write_node)
    anatomy = Anatomy()
    directory_template = anatomy.templates["publish"]["render"]["directory"]
    file_termplate = anatomy.templates["publish"]["render"]["file"]

    root = anatomy.roots["work"].value.rstrip("/")
    project_name = context["project_name"]
    hierarchy = Path(context["folder_path"].lstrip("/")).parent
    shot = Path(context["folder_path"]).name
    product = get_publish_instance_data(ayon_write_node)["productType"]
    name = get_publish_instance_data(ayon_write_node)["productName"]
    version = 0  # temp value so we can parse the template

    # directory_data = {
    #     "root": {"work": root},
    #     "project": {"name": project_name},
    #     "hierarchy": hierarchy,
    #     "folder": {"name": shot},
    #     "product": {"type": product, "name": name},
    #     "version": version,
    # }

    publish_path = Path(
        directory_template.format_map(
            {
                "root": {"work": root},
                "project": {"name": project_name},
                "hierarchy": hierarchy,
                "folder": {"name": shot},
                "product": {"type": product, "name": name},
                "version": version,
            }
        )
    ).parent

    print(f"Publish path: {publish_path}")
    nuke.tprint(f"Publish path: {publish_path}")

    try:
        newest_version = Path(
            sorted([d.name for d in publish_path.iterdir() if d.is_dir()])[-1]
        )
    except IndexError:
        print("No versions, has it been published?")
        log.error("No versions, has it been published?")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        log.error(f"Unexpected error: {e}")
        return

    publish_path /= newest_version
    log.info(f"Publish path: {publish_path}")

    extension = ayon_write_node["file_type"].value()



    # first_frame = int(ayon_write_node["Render Start"].getValue())
    # last_frame = int(ayon_write_node["Render End"].getValue())
    # pad_count = len(str(last_frame))

    # file_data = {
    #     "folder": {"name": shot},
    #     "product": {"type": product, "name": name},
    #     "version": newest_version,
    #     "output": "",  # TODO what is this?
    #     "extension": extension,
    # }
    
    """
    Ideally we would query the database for products to get the latest version, 
    and parse "file_template" to get the file name. 
    
    For now I am finding the latest version from the file system, and 
    using FileSequence lib to extract a valid image sequence from that location
    """

    

    seqs = FileSequence.match_components_in_path(
        Components(
            extension=extension,
        ),
        publish_path,
    )

    if not seqs:
        print("No sequence found")
        return

    sequence = seqs[0]
    string = sequence.sequence_string(sequence.StringVariant.NUKE)

    result = publish_path / string
    
    print(f"Publish path: {result}")
    nuke.tprint(f"Publish path: {result}")
    
    # return str(result)
    return result



def read_from_publish(ayon_write_node):
    if (ayon_write_node) is None:
        log.error("ayon_write_node is None")
        nuke.tprint("ayon_write_node is None")

    with nuke.toNode("root"):
        ppath = assemble_publish_path(ayon_write_node)
        if not ppath:
            return
        publish_path = ppath.as_posix()

        if (publish_path) is None:
            return

        read_node = nuke.nodes.Read()
        read_node["file"].fromUserText(publish_path)

        read_node.setXYpos(
            int(ayon_write_node["xpos"].getValue()),
            int(ayon_write_node["ypos"].getValue()) + 60,
        )


def get_publish_instance_data(write_node):
    # parse the json data from the write node

    return json.loads(
        write_node["publish_instance"].value().replace("JSON:::", "")
    )



def navigate_to_render(write_node):
    ''' Open explorer at the location of the render file

    Args:
        Ayon write node

    ''' 

    file_path = Path(write_node['File output'].evaluate()).parent
    if not file_path.exists():
        return

    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", file_path])
    else:  # Linux
        subprocess.run(["xdg-open", file_path])


def navigate_to_publish(write_node):

    ''' Open explorer at the location of the publish file

    Args:
        Ayon write node

    ''' 

    path = assemble_publish_path(write_node)
    if not path:
        return
    path = path.parent

    print(f"Publish path: {path}")

    if not path.exists():
        return



    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.run(["open", path])
    else:  # Linux
        subprocess.run(["xdg-open", path])
        




def filter_write_nodes(nodes):

    filtered_nodes = [n for n in nodes if n.Class() == "Group" and 'publish_instance' in n.knobs() and "submit" in n.knobs()]

    return filtered_nodes






