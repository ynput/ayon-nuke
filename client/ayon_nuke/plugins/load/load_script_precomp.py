import nuke
from ayon_core.pipeline import get_representation_path
from ayon_nuke.api import (
    containerise,
    plugin,
    update_container,
)
from ayon_nuke.api.command import undo_chunk
from ayon_nuke.api.lib import color_to_int, get_avalon_knob_data


class LinkAsGroup(plugin.NukeLoader):
    """Copy the published file to be pasted at the desired location"""

    product_base_types = {"workfile", "nukenodes"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {"nk"}

    settings_category = "nuke"

    label = "Load Precomp"
    order = 0
    icon = "file"

    node_color_latest =   color_to_int(255, 255, 255)  # 0xff0ff0ff
    node_color_outdated = color_to_int(216, 79, 32)    # 0xd84f20ff

    @undo_chunk("Load Precomp")
    def load(self, context, name, namespace, data):
        # for k, v in context.items():
        #     log.info("key: `{}`, value: {}\n".format(k, v))
        version_entity = context["version"]

        version_attributes = version_entity["attrib"]
        first = version_attributes.get("frameStart")
        last = version_attributes.get("frameEnd")
        colorspace = version_attributes.get("colorSpace")

        # Fallback to folder name when namespace is None
        if namespace is None:
            namespace = context["folder"]["name"]

        file = self.filepath_from_context(context).replace("\\", "/")
        self.log.info("file: {}\n".format(file))

        data_imprint = {
            "startingFrame": first,
            "frameStart": first,
            "frameEnd": last,
            "version": version_entity["version"]
        }
        # add additional metadata from the version to imprint to Avalon knob
        for k in [
            "frameStart",
            "frameEnd",
            "handleStart",
            "handleEnd",
            "source",
            "fps"
        ]:
            data_imprint[k] = version_attributes[k]

        # group context is set to precomp, so back up one level.
        nuke.endGroup()

        # P = nuke.nodes.LiveGroup("file {}".format(file))
        P = nuke.createNode(
            "Precomp",
            "file {}".format(file),
            inpanel=False
        )

        # Set colorspace defined in version data
        self.log.info("colorspace: {}\n".format(colorspace))

        P.setName(f"{name}_{namespace}")
        P["useOutput"].setValue(True)

        with P:
            # iterate through all nodes in group node and find AYON writes
            writes = [n.name() for n in nuke.allNodes()
                      if n.Class() == "Group"
                      if get_avalon_knob_data(n)]

            if writes:
                # create panel for selecting output
                panel_choices = " ".join(writes)
                panel_label = "Select write node for output"
                p = nuke.Panel("Select Write Node")
                p.addEnumerationPulldown(
                    panel_label, panel_choices)
                p.show()
                P["output"].setValue(p.value(panel_label))

        container = containerise(
            node=P,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
            data=data_imprint,
        )
        self.update_node_color(P)  # after containerise
        return container

    def switch(self, container, context):
        self.update(container, context)

    @undo_chunk("Update Precomp")
    def update(self, container, context):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """
        node = container["node"]
        version_entity = context["version"]
        repre_entity = context["representation"]

        root = get_representation_path(repre_entity).replace("\\", "/")

        # Get start frame from version data

        version_attributes = version_entity["attrib"]
        updated_dict = {
            "representation": repre_entity["id"],
            "frameEnd": version_attributes.get("frameEnd"),
            "version": version_entity["version"],
            "colorspace": version_attributes.get("colorSpace"),
            "source": version_attributes.get("source"),
            "fps": version_attributes.get("fps"),
        }

        # Update the imprinted representation
        update_container(
            node,
            updated_dict
        )

        node["file"].setValue(root)

        self.update_node_color(node)  # after update_container
        self.log.info(
            "updated to version: {}".format(version_entity["version"])
        )
        return container

    @undo_chunk("Remove Precomp")
    def remove(self, container):
        node = container["node"]
        nuke.delete(node)
