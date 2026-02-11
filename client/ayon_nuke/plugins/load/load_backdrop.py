import contextlib
import nuke
import nukescripts
import ayon_api

from ayon_core.pipeline import load
from ayon_nuke.api.lib import (
    find_free_space_to_paste_nodes,
    maintained_selection,
    reset_selection,
    select_nodes,
    get_avalon_knob_data,
    set_avalon_knob_data
)
from ayon_nuke.api.command import viewer_update_and_undo_stop
from ayon_nuke.api import containerise, update_container


class LoadBackdropNodes(load.LoaderPlugin):
    """Loading published .nk files to backdrop nodes"""

    product_types = {"*"}
    representations = {"*"}
    extensions = {"nk"}

    settings_category = "nuke"

    label = "Import Nuke Nodes"
    order = 0
    icon = "eye"
    color = "white"
    node_color = "0x7533c1ff"
    remove_nodes_from_backdrop = False

    def load(self, context, name, namespace, data):
        """
        Loading function to import .nk file into script and wrap
        it on backdrop

        Arguments:
            context (dict): context of version
            name (str): name of the version
            namespace (str): namespace name
            data (dict): compulsory attribute > not used

        Returns:
            nuke node: containerised nuke node object
        """

        # get main variables
        namespace = namespace or context["folder"]["name"]
        version_entity = context["version"]

        version_attributes = version_entity["attrib"]
        colorspace = version_attributes.get("colorSpace")

        object_name = "{}_{}".format(name, namespace)

        # prepare data for imprinting
        data_imprint = {
            "version": version_entity["version"],
            "colorspaceInput": colorspace
        }

        # add attributes from the version to imprint to metadata knob
        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes[k]

        # getting file path
        file = self.filepath_from_context(context).replace("\\", "/")

        # adding nodes to node graph
        # just in case we are in group lets jump out of it
        nuke.endGroup()

        # Get mouse position
        n = nuke.createNode("NoOp")
        xcursor, ycursor = (n.xpos(), n.ypos())
        reset_selection()
        nuke.delete(n)

        bdn_frame = 50

        with maintained_selection():

            # add group from nk
            nuke.nodePaste(file)

            # get all pasted nodes
            new_nodes = list()
            nodes = nuke.selectedNodes()

            # get pointer position in DAG
            xpointer, ypointer = find_free_space_to_paste_nodes(
                nodes, direction="right", offset=200 + bdn_frame
            )

            # reset position to all nodes and replace inputs and output
            for n in nodes:
                reset_selection()
                xpos = (n.xpos() - xcursor) + xpointer
                ypos = (n.ypos() - ycursor) + ypointer
                n.setXYpos(xpos, ypos)

                # replace Input nodes for dots
                if n.Class() in "Input":
                    dot = nuke.createNode("Dot")
                    new_name = n.name().replace("INP", "DOT")
                    dot.setName(new_name)
                    dot["label"].setValue(new_name)
                    dot.setXYpos(xpos, ypos)
                    new_nodes.append(dot)

                    # rewire
                    dep = n.dependent()
                    for d in dep:
                        index = next((i for i, dpcy in enumerate(
                                      d.dependencies())
                                      if n is dpcy), 0)
                        d.setInput(index, dot)

                    # remove Input node
                    reset_selection()
                    nuke.delete(n)
                    continue

                # replace Input nodes for dots
                elif n.Class() in "Output":
                    dot = nuke.createNode("Dot")
                    new_name = n.name() + "_DOT"
                    dot.setName(new_name)
                    dot["label"].setValue(new_name)
                    dot.setXYpos(xpos, ypos)
                    new_nodes.append(dot)

                    # rewire
                    dep = next((d for d in n.dependencies()), None)
                    if dep:
                        dot.setInput(0, dep)

                    # remove Input node
                    reset_selection()
                    nuke.delete(n)
                    continue
                else:
                    new_nodes.append(n)

            # reselect nodes with new Dot instead of Inputs and Output
            reset_selection()
            select_nodes(new_nodes)
            # place on backdrop
            bdn = self.set_autobackdrop(xpos, ypos, object_name)
            return containerise(
                node=bdn,
                name=name,
                namespace=namespace,
                context=context,
                loader=self.__class__.__name__,
                data=data_imprint)

    def update(self, container, context):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """

        # get main variables
        # Get version from io
        project_name = context["project"]["name"]
        version_entity = context["version"]
        repre_entity = context["representation"]

        # get corresponding node
        GN = container["node"]

        file = self.filepath_from_context(context).replace("\\", "/")

        name = container["name"]
        namespace = container["namespace"]
        object_name = "{}_{}".format(name, namespace)

        version_attributes = version_entity["attrib"]
        colorspace = version_attributes.get("colorSpace")

        data_imprint = {
            "representation": repre_entity["id"],
            "version": version_entity["version"],
            "colorspaceInput": colorspace,
        }

        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes[k]

        # adding nodes to node graph
        # just in case we are in group lets jump out of it
        nuke.endGroup()

        xpos = GN.xpos()
        ypos = GN.ypos()
        avalon_data = get_avalon_knob_data(GN)

        # Preserve external connections (to/from outside the backdrop)
        backdrop_nodes = GN.getNodes()
        with restore_node_connections(backdrop_nodes):
            for node in backdrop_nodes:
                # Delete old backdrop nodes
                nuke.delete(node)
            nuke.delete(GN)

            with maintained_selection():
                # add group from nk
                nuke.nodePaste(file)
                # create new backdrop so that the nodes can be
                # filled within it
                GN = self.set_autobackdrop(xpos, ypos, object_name)
                set_avalon_knob_data(GN, avalon_data)

        # get all versions in list
        last_version_entity = ayon_api.get_last_version_by_product_id(
            project_name, version_entity["productId"], fields={"id"}
        )

        # change color of node
        if version_entity["id"] == last_version_entity["id"]:
            color_value = self.node_color
        else:
            color_value = "0xd88467ff"
        GN["tile_color"].setValue(int(color_value, 16))

        self.log.info(
            "updated to version: {}".format(version_entity["version"])
        )

        return update_container(GN, data_imprint)

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = container["node"]
        with viewer_update_and_undo_stop():
            if self.remove_nodes_from_backdrop:
                for child_node in node.getNodes():
                    nuke.delete(child_node)
            nuke.delete(node)

    def set_autobackdrop(self, xpos, ypos, object_name, bdn_frame=50):
        """Set auto backdrop around selected nodes

        Args:
            xpos (int): x position
            ypos (int): y position
            object_name (str): name of the object
            bdn_frame (int, optional): frame size around the backdrop. Defaults to 50.

        Returns:
            nuke.BackdropNode: the created backdrop node
        """
        # place on backdrop
        bdn = nukescripts.autoBackdrop()

        # add frame offset
        xpos = bdn.xpos() - bdn_frame
        ypos = bdn.ypos() - bdn_frame
        bdwidth = bdn["bdwidth"].value() + (bdn_frame*2)
        bdheight = bdn["bdheight"].value() + (bdn_frame*2)

        bdn["xpos"].setValue(xpos)
        bdn["ypos"].setValue(ypos)
        bdn["bdwidth"].setValue(bdwidth)
        bdn["bdheight"].setValue(bdheight)

        bdn["name"].setValue(object_name)
        bdn["label"].setValue("Version tracked frame: \n`{}`\n\nPLEASE DO NOT REMOVE OR MOVE \nANYTHING FROM THIS FRAME!".format(object_name))
        bdn["note_font_size"].setValue(20)

        return bdn

def _get_expression_safe(knob):
    """Safely get expression from a knob.

    Args:
        knob: Nuke knob object to check.

    Returns:
        str: Expression string if exists, None otherwise.
    """
    if knob and hasattr(knob, 'expression'):
        expr = knob.expression()
        return expr if expr else None
    return None


def _restore_connection(conn, node_map):
    """Restore a single node connection or expression.

    Args:
        conn (dict): Connection dictionary with serialized node names and metadata.
        node_map (dict): Mapping of node names to actual node objects.
    """
    if "input_node_name" in conn:
        # Restore incoming connections
        node_name = conn["node_name"]
        input_node_name = conn["input_node_name"]

        if node_name not in node_map or input_node_name not in node_map:
            return

        node = node_map[node_name]
        input_node = node_map[input_node_name]
        input_index = conn["input_index"]

        # Restore connection
        if conn.get("expression"):
            node.input(input_index).setExpression(conn["expression"])
        else:
            node.setInput(input_index, input_node)
    else:
        # Restore outgoing connections
        node_name = conn["node_name"]
        dependent_name = conn["dependent_name"]

        if node_name not in node_map or dependent_name not in node_map:
            return

        node = node_map[node_name]
        dependent = node_map[dependent_name]
        input_index = conn["dependent_input_index"]

        # Restore connection
        if conn.get("expression"):
            dependent.input(input_index).setExpression(conn["expression"])
        else:
            dependent.setInput(input_index, node)


def _capture_node_connections(backdrop_nodes):
    """Capture only external connections (to/from nodes outside the backdrop).

    Does not capture connections between nodes within the backdrop itself.
    Serializes connection data to avoid "PythonObject not attached" errors
    when nodes are deleted and recreated.

    Args:
        backdrop_nodes (list): List of nodes to capture external connections for.

    Returns:
        list: List of connection dictionaries with serialized node names.
    """
    connections = []
    filtered_backdrop_nodes = {node.name() for node in backdrop_nodes}

    for node in backdrop_nodes:
        node_name = node.name()

        # Incoming connections from OUTSIDE the backdrop only
        for input_index in range(node.inputs()):
            input_node = node.input(input_index)
            if input_node and input_node.name() not in filtered_backdrop_nodes:
                # Capture expression if it exists
                knob = node.input(input_index)
                expr = _get_expression_safe(knob)
                connections.append({
                    "node_name": node_name,
                    "input_index": input_index,
                    "input_node_name": input_node.name(),
                    "expression": expr,
                })

        # Outgoing connections to OUTSIDE the backdrop only
        for dependent in node.dependent():
            for input_index, depcy in enumerate(dependent.dependencies()):
                if node is depcy:
                    # Capture expression if it exists
                    knob = dependent.input(input_index)
                    expr = _get_expression_safe(knob)
                    connections.append({
                        "node_name": node_name,
                        "dependent_name": dependent.name(),
                        "dependent_input_index": input_index,
                        "expression": expr,
                    })

    return connections


@contextlib.contextmanager
def restore_node_connections(backdrop_nodes):
    """Context manager to capture and restore node connections.

    Captures all incoming and outgoing connections before backdrop nodes
    are deleted, then restores them after new nodes are pasted.
    Uses serialized node names to avoid "PythonObject not attached" errors.

    Args:
        backdrop_nodes (list): List of nodes whose connections to preserve.

    Yields:
        None
    """
    original_connections = _capture_node_connections(backdrop_nodes)
    try:
        yield
    finally:
        # Build node map by name from current nodes
        node_map = {
            node.name(): node
            for node in nuke.allNodes()
        }
        # Restore connections using the node map
        for conn in original_connections:
            _restore_connection(conn, node_map)
