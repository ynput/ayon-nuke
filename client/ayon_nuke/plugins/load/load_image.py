import nuke

import ayon_api

from ayon_core.pipeline import load

from ayon_nuke.api.command import undo_chunk

from ayon_core.lib import NumberDef
from ayon_nuke.api import (
    containerise,
    update_container,
)
from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS
)
from ayon_nuke.api.load_traits import LoadRepresentation
from ayon_nuke.api.load_utils import set_read_colorspace

from typing import Optional

class LoadImage(load.LoaderPlugin):
    """Load still image into Nuke"""

    product_base_types = {
        "render2d",
        "source",
        "plate",
        "render",
        "prerender",
        "review",
        "image",
        "workfile"
    }
    product_types = product_base_types
    representations = {"*"}
    extensions = set(ext.lstrip(".") for ext in IMAGE_EXTENSIONS)

    settings_category = "nuke"

    label = "Load Image"
    order = -10
    icon = "image"
    color = "white"

    # Loaded from settings
    representations_include = []

    node_name_template = "{class_name}_{ext}"

    options = [
        NumberDef(
            "frame_number",
            label="Frame Number",
            default=int(nuke.root()["first_frame"].getValue()),
            minimum=1,
            maximum=999999,
            tooltip="What frame is reading from?"
        )
    ]

    @classmethod
    def get_representations(cls):
        return cls.representations_include or cls.representations

    @undo_chunk("Load Image")
    def load(self, context, name, namespace, options):
        project_name = context["project"]["name"]

        self.log.info("__ options: `{}`".format(options))
        frame_number = options.get(
            "frame_number", int(nuke.root()["first_frame"].getValue())
        )

        version_entity = context["version"]
        # representation traits - legacy representation is converted
        load_repre = LoadRepresentation.from_context(context)
        version_attributes = load_repre.version_attributes
        repre_entity = context["representation"]
        repre_id = repre_entity["id"]

        self.log.debug(
            "Representation id `{}` ".format(repre_id))

        last = first = int(frame_number)

        # Fallback to folder name when namespace is None
        if namespace is None:
            namespace = context["folder"]["name"]

        filepath = self._get_filepath(load_repre, frame_number)
        if not filepath:
            self.log.warning(
                "Representation id `{}` is failing to load".format(repre_id))
            return

        read_name = self._get_node_name(context)

        # Create the Loader with the filename path set
        read_node = nuke.createNode(
            "Read", "name {}".format(read_name), inpanel=False
        )

        self.set_colorspace_to_node(
            read_node,
            filepath,
            project_name,
            load_repre,
        )

        read_node["file"].setValue(filepath)
        read_node["origfirst"].setValue(first)
        read_node["first"].setValue(first)
        read_node["origlast"].setValue(last)
        read_node["last"].setValue(last)

        # add attributes from the version to imprint metadata knob
        data_imprint = {
            "frameStart": first,
            "frameEnd": last,
            "version": version_entity["version"]
        }
        for k in ["source", "fps"]:
            data_imprint[k] = version_attributes.get(k, str(None))

        read_node["tile_color"].setValue(int("0x4ecd25ff", 16))

        return containerise(
            read_node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
            data=data_imprint,
        )

    def switch(self, container, context):
        self.update(container, context)

    @undo_chunk("Update Image")
    def update(self, container, context):
        """Update the Loader's path

        Nuke automatically tries to reset some variables when changing
        the loader's path to a new file. These automatic changes are to its
        inputs:

        """
        read_node = container["node"]
        frame_number = read_node["first"].value()

        assert read_node.Class() == "Read", "Must be Read"

        project_name = context["project"]["name"]
        version_entity = context["version"]
        repre_entity = context["representation"]
        # representation traits - legacy representation is converted
        load_repre = LoadRepresentation.from_context(context)

        filepath = self._get_filepath(load_repre, frame_number)
        if not filepath:
            repre_id = repre_entity["id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repre_id))
            return

        # Get start frame from version data
        last_version_entity = ayon_api.get_last_version_by_product_id(
            project_name, version_entity["productId"], fields={"id"}
        )

        last = first = int(frame_number)

        self.set_colorspace_to_node(
            read_node,
            filepath,
            project_name,
            load_repre,
        )
        # Set the global in to the start frame of the sequence
        read_node["file"].setValue(filepath)
        read_node["origfirst"].setValue(first)
        read_node["first"].setValue(first)
        read_node["origlast"].setValue(last)
        read_node["last"].setValue(last)

        version_attributes = load_repre.version_attributes
        updated_dict = {
            "representation": repre_entity["id"],
            "frameStart": str(first),
            "frameEnd": str(last),
            "version": str(version_entity["version"]),
            "source": version_attributes.get("source"),
            "fps": str(version_attributes.get("fps")),
            "project_name": project_name,
        }

        # change color of node
        if version_entity["id"] == last_version_entity["id"]:
            color_value = "0x4ecd25ff"
        else:
            color_value = "0xd84f20ff"
        read_node["tile_color"].setValue(int(color_value, 16))

        # Update the imprinted representation
        update_container(read_node, updated_dict)
        self.log.info("updated to version: {}".format(
            version_entity["version"]
        ))

    @undo_chunk("Remove Image")
    def remove(self, container):
        node = container["node"]
        assert node.Class() == "Read", "Must be Read"
        nuke.delete(node)

    def _get_filepath(
            self, load_repre: LoadRepresentation,
            frame_number: int) -> Optional[str]:
        """Path to the image of the frame.

        Args:
            load_repre (LoadRepresentation): Loaded representation.
            frame_number (int): Frame number to load from a sequence.

        Returns:
            Optional[str]: File path.

        """
        frame_range = load_repre.frame_range
        if (
            not load_repre.is_converted
            and load_repre.is_sequence
            and frame_range is not None
            and not (
                frame_range.frame_start
                <= int(frame_number)
                <= frame_range.frame_end
            )
        ):
            self.log.warning(
                "Frame {frame} is out of frame range"
                " {frame_start}-{frame_end} of representation"
                " {representation_id}",
                frame=frame_number,
                frame_start=frame_range.frame_start,
                frame_end=frame_range.frame_end,
                representation_id=load_repre.repre_entity["id"],
            )
        return load_repre.get_file_path(frame=frame_number)

    def _get_node_name(self, context):
        folder_entity = context["folder"]
        product_name = context["product"]["name"]
        repre_entity = context["representation"]

        folder_name = folder_entity["name"]
        repre_cont = repre_entity["context"]
        name_data = {
            "folder": {
                "name": folder_name,
            },
            "product": {
                "name": product_name,
            },
            "asset": folder_name,
            "subset": product_name,
            "representation": repre_entity["name"],
            "ext": repre_cont["representation"],
            "id": repre_entity["id"],
            "class_name": self.__class__.__name__
        }

        return self.node_name_template.format(**name_data)

    def set_colorspace_to_node(
        self,
        read_node,
        filepath,
        project_name,
        load_repre,
    ):
        """Set colorspace to read node.

        Sets colorspace with available names validation.

        Args:
            read_node (nuke.Node): The nuke's read node
            filepath (str): File path.
            project_name (str): Project name.
            load_repre (LoadRepresentation): Loaded representation.

        """
        set_read_colorspace(
            read_node,
            project_name,
            filepath,
            load_repre.colorspace,
            logger=self.log,
        )
