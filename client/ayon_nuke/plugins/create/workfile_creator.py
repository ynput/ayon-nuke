import ayon_nuke.api as api
from ayon_core.pipeline import (
    AutoCreator,
    CreatedInstance,
)
from ayon_nuke.api import (
    INSTANCE_DATA_KNOB,
    set_node_data
)
import nuke


class WorkfileCreator(AutoCreator):

    settings_category = "nuke"
    is_mandatory = False

    identifier = "workfile"
    product_type = "workfile"
    product_base_type = "workfile"

    default_variant = "Main"

    def get_instance_attr_defs(self):
        return []

    def collect_instances(self):
        root_node = nuke.root()
        instance_data = api.get_node_data(
            root_node, api.INSTANCE_DATA_KNOB
        )

        project_entity = self.create_context.get_current_project_entity()
        folder_entity = self.create_context.get_current_folder_entity()
        task_entity = self.create_context.get_current_task_entity()

        project_name = project_entity["name"]
        folder_path = folder_entity["path"]
        task_name = task_entity["name"]
        host_name = self.create_context.host_name

        product_name = self.get_product_name(
            project_name=project_name,
            project_entity=project_entity,
            folder_entity=folder_entity,
            task_entity=task_entity,
            variant=self.default_variant,
            host_name=host_name,
        )
        instance_data.update({
            "folderPath": folder_path,
            "task": task_name,
            "variant": self.default_variant
        })
        instance_data.update(self.get_dynamic_data(
            project_name,
            folder_entity,
            task_entity,
            self.default_variant,
            host_name,
            instance_data
        ))

        instance = CreatedInstance(
            self.product_type, product_name, instance_data, self
        )
        if hasattr(instance, "set_mandatory"):
            instance.set_mandatory(self.is_mandatory)
        instance.transient_data["node"] = root_node
        self._add_instance_to_context(instance)

    def update_instances(self, update_list):
        for created_inst, _changes in update_list:
            instance_node = created_inst.transient_data["node"]

            set_node_data(
                instance_node,
                INSTANCE_DATA_KNOB,
                created_inst.data_to_store()
            )

    def create(self, options=None):
        # no need to create if it is created
        # in `collect_instances`
        pass
