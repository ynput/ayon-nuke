import six
import sys
from ayon_nuke.api import (
    INSTANCE_DATA_KNOB,
    NukeCreator,
    NukeCreatorError,
    set_node_data
)
from ayon_core.pipeline import (
    CreatedInstance
)


class CreateSource(NukeCreator):
    """Add Publishable Read with source"""

    settings_category = "nuke"

    identifier = "create_source"
    label = "Source (read)"
    product_type = "source"
    icon = "film"
    default_variants = ["Effect", "Backplate", "Fire", "Smoke"]

    # plugin attributes
    node_color = "0xff9100ff"

    def create_instance_node(
        self,
        node_name,
        read_node
    ):
        read_node["tile_color"].setValue(
            int(self.node_color, 16))
        read_node["name"].setValue(node_name)

        return read_node

    def create(self, product_name, instance_data, pre_create_data):

        # make sure selected nodes are added
        self._set_selected_nodes(pre_create_data)

        try:
            for read_node in self.selected_nodes:
                if read_node.Class() != 'Read':
                    continue

                node_name = read_node.name()
                _product_name = product_name + node_name

                # make sure product name is unique
                self.check_existing_product(_product_name)

                instance_node = self.create_instance_node(
                    _product_name,
                    read_node
                )
                instance = CreatedInstance(
                    self.product_type,
                    _product_name,
                    instance_data,
                    self
                )

                # add staging dir related data to transient data
                self.apply_staging_dir(instance)

                instance.transient_data["node"] = instance_node

                self._add_instance_to_context(instance)

                set_node_data(
                    instance_node,
                    INSTANCE_DATA_KNOB,
                    instance.data_to_store()
                )

        except Exception as er:
            six.reraise(
                NukeCreatorError,
                NukeCreatorError("Creator error: {}".format(er)),
                sys.exc_info()[2])

    def _set_selected_nodes(self, pre_create_data):
        """ Ensure provided selection is valid.

        Args:
            pre_create_data (dict): The pre-create data.

        Raises:
            NukeCreatorError. When provided selection is invalid.
        """
        if not pre_create_data.get("use_selection"):
            raise NukeCreatorError(
                "Creator error: only supported with active selection"
            )

        super()._set_selected_nodes(pre_create_data)