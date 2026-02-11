import nuke

import qargparse
import ayon_api

from ayon_core.pipeline import load

from ayon_nuke.api.lib import (
    get_imageio_input_colorspace
)
from ayon_core.pipeline.colorspace import (
    get_imageio_file_rules_colorspace_from_filepath,
    get_current_context_imageio_config_preset,
)
from ayon_nuke.api import (
    containerise,
    update_container,
    viewer_update_and_undo_stop,
    colorspace_exists_on_node,
)
from ayon_core.lib.transcoding import (
    IMAGE_EXTENSIONS
)


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
        qargparse.Integer(
            "frame_number",
            label="Frame Number",
            default=int(nuke.root()["first_frame"].getValue()),
            min=1,
            max=999999,
            help="What frame is reading from?"
        )
    ]

    @classmethod
    def get_representations(cls):
        return cls.representations_include or cls.representations

    def load(self, context, name, namespace, options):
        project_name = context["project"]["name"]
        repre_entity = context["representation"]
        version_entity = context["version"]

        self.log.info("__ options: `{}`".format(options))
        frame_number = options.get(
            "frame_number", int(nuke.root()["first_frame"].getValue())
        )

        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        repre_entity = context["representation"]
        repre_id = repre_entity["id"]

        self.log.debug(
            "Representation id `{}` ".format(repre_id))

        last = first = int(frame_number)

        # Fallback to folder name when namespace is None
        if namespace is None:
            namespace = context["folder"]["name"]

        filepath = self.filepath_from_context(context)

        if not filepath:
            self.log.warning(
                "Representation id `{}` is failing to load".format(repre_id))
            return

        filepath = filepath.replace("\\", "/")

        frame = repre_entity["context"].get("frame")
        if frame:
            padding = len(frame)
            filepath = filepath.replace(
                frame, format(frame_number, "0{}".format(padding))
            )

        read_name = self._get_node_name(context)

        # Create the Loader with the filename path set
        with viewer_update_and_undo_stop():
            read_node = nuke.createNode(
                "Read", "name {}".format(read_name), inpanel=False
            )

            self.set_colorspace_to_node(
                read_node,
                filepath,
                project_name,
                version_entity,
                repre_entity
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

        repr_cont = repre_entity["context"]

        filepath = self.filepath_from_context(context)

        if not filepath:
            repre_id = repre_entity["id"]
            self.log.warning(
                "Representation id `{}` is failing to load".format(repre_id))
            return

        filepath = filepath.replace("\\", "/")

        frame = repr_cont.get("frame")
        if frame:
            padding = len(frame)
            filepath = filepath.replace(
                frame, format(frame_number, "0{}".format(padding))
            )

        # Get start frame from version data
        last_version_entity = ayon_api.get_last_version_by_product_id(
            project_name, version_entity["productId"], fields={"id"}
        )

        last = first = int(frame_number)

        self.set_colorspace_to_node(
            read_node, filepath, project_name, version_entity, repre_entity
        )
        # Set the global in to the start frame of the sequence
        read_node["file"].setValue(filepath)
        read_node["origfirst"].setValue(first)
        read_node["first"].setValue(first)
        read_node["origlast"].setValue(last)
        read_node["last"].setValue(last)

        version_attributes = version_entity["attrib"]
        updated_dict = {
            "representation": repre_entity["id"],
            "frameStart": str(first),
            "frameEnd": str(last),
            "version": str(version_entity["version"]),
            "source": version_attributes.get("source"),
            "fps": str(version_attributes.get("fps")),
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

    def remove(self, container):
        node = container["node"]
        assert node.Class() == "Read", "Must be Read"

        with viewer_update_and_undo_stop():
            nuke.delete(node)

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
        version_entity,
        repre_entity,
    ):
        """Set colorspace to read node.

        Sets colorspace with available names validation.

        Args:
            read_node (nuke.Node): The nuke's read node
            filepath (str): File path.
            project_name (str): Project name.
            version_entity (dict): Version entity.
            repre_entity (dict): Representation entity.

        """
        used_colorspace = self._get_colorspace_data(
            project_name, version_entity, repre_entity, filepath
        )
        if (
            used_colorspace
            and colorspace_exists_on_node(read_node, used_colorspace)
        ):
            self.log.info(f"Used colorspace: {used_colorspace}")
            read_node["colorspace"].setValue(used_colorspace)
        else:
            self.log.info("Colorspace not set...")

    def _get_colorspace_data(
        self, project_name, version_entity, repre_entity, filepath
    ):
        """Get colorspace data from version and representation documents

        Args:
            project_name (str): Project name.
            version_entity (dict): Version entity.
            repre_entity (dict): Representation entity.
            filepath (str): File path.

        Returns:
            Any[str,None]: colorspace name or None
        """
        # Get colorspace from representation colorspaceData if colorspace is
        # not found.
        colorspace_data = repre_entity["data"].get("colorspaceData", {})
        colorspace = colorspace_data.get("colorspace")
        self.log.debug(
            f"Colorspace from representation colorspaceData: {colorspace}")

        if not colorspace:
            # Get backward compatible colorspace key.
            colorspace = repre_entity["data"].get("colorspace")
            self.log.debug(
                f"Colorspace from representation colorspace: {colorspace}")

        # Get backward compatible version data key if colorspace is not found.
        if not colorspace:
            colorspace = version_entity["attrib"].get("colorSpace")
            self.log.debug(
                f"Colorspace from version colorspace: {colorspace}")

        config_data = get_current_context_imageio_config_preset()
        # check if any filerules are not applicable
        new_parsed_colorspace = get_imageio_file_rules_colorspace_from_filepath(  # noqa
            filepath, "nuke", project_name, config_data=config_data
        )
        self.log.debug(f"Colorspace new filerules: {new_parsed_colorspace}")

        # colorspace from `project_settings/nuke/imageio/regexInputs`
        old_parsed_colorspace = get_imageio_input_colorspace(filepath)
        self.log.debug(f"Colorspace old filerules: {old_parsed_colorspace}")

        return new_parsed_colorspace or old_parsed_colorspace or colorspace
