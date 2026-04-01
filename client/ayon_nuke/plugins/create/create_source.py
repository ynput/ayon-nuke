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
    product_base_type = "source"
    product_type = product_base_type
    icon = "film"
    default_variants = ["Effect", "Backplate", "Fire", "Smoke"]

    # plugin attributes
    node_color = "0xff9100ff"
    node_class_name = "Read"

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
        node_selection = self._get_current_selected_nodes(
            pre_create_data,
            class_name=self.node_class_name
        )

        try:
            for read_node in node_selection:

                node_name = read_node.name()
                _product_name = product_name + node_name

                # make sure product name is unique
                self.check_existing_product(_product_name)

                instance_node = self.create_instance_node(
                    _product_name,
                    read_node
                )
                product_type = instance_data.get("productType")
                if not product_type:
                    product_type = self.product_base_type
                instance = CreatedInstance(
                    product_base_type=self.product_base_type,
                    product_type=product_type,
                    product_name=_product_name,
                    data=instance_data,
                    creator=self,
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

        except Exception as exc:
            raise NukeCreatorError(f"Creator error: {exc}") from exc
