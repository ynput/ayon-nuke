from __future__ import annotations

import typing

import pyblish.api
import ayon_api

from ayon_core.lib.attribute_definitions import (
    TextDef,
    BoolDef,
)
from ayon_core.pipeline.publish import AYONPyblishPluginMixin
if typing.TYPE_CHECKING:
    from ayon_core.pipeline.create import CreatedInstance, CreateContext
    from ayon_core.lib.attribute_definitions import AbstractAttrDef


NOT_SET = object()


class CollectFramesFixDefNuke(
    pyblish.api.InstancePlugin,
    AYONPyblishPluginMixin
):
    """Provides text field to insert frame(s) to be rerendered.

    Published files of last version of an instance product are collected into
    instance.data["last_version_published_files"]. All these but frames
    mentioned in text field will be reused for new version.
    """
    order = pyblish.api.CollectorOrder + 0.495
    label = "Collect Frames to Fix"
    targets = ["local"]
    hosts = ["nuke"]
    families = ["render", "prerender"]
    settings_category = "nuke"

    rewrite_version_enable = False

    core_plugin = NOT_SET

    def process(self, instance):
        attribute_values = self.get_attr_values_from_data(instance.data)
        frames_to_fix = attribute_values.get("frames_to_fix")

        rewrite_version = attribute_values.get("rewrite_version")

        if not frames_to_fix:
            return

        instance.data["frames_to_fix"] = frames_to_fix

        product_name = instance.data["productName"]
        folder_entity = instance.data["folderEntity"]

        project_entity = instance.data["projectEntity"]
        project_name = project_entity["name"]

        version_entity = ayon_api.get_last_version_by_product_name(
            project_name,
            product_name=product_name,
            folder_id=folder_entity["id"],
        )
        if not version_entity:
            self.log.warning(
                "No last version found, re-render not possible"
            )
            return

        product_entity = ayon_api.get_product_by_id(
            project_name, version_entity["productId"]
        )
        product_base_type = product_entity["productBaseType"]
        published_files = []
        if product_base_type in self.families:
            representations = ayon_api.get_representations(
                project_name, version_ids={version_entity["id"]}
            )
            for repre in representations:
                published_files.extend(
                    file_info["path"]
                    for file_info in repre["files"]
                )

        instance.data["last_version_published_files"] = published_files
        self.log.debug("last_version_published_files::{}".format(
            instance.data["last_version_published_files"]))

        if self.rewrite_version_enable and rewrite_version:
            instance.data["version"] = version_entity["version"]
            # limits triggering version validator
            instance.data.pop("latestVersion")

    @classmethod
    def get_attr_defs_for_instance(
        cls, create_context: CreateContext, instance: CreatedInstance
    ) -> list[AbstractAttrDef]:
        if not cls.handle_backwards_compatibility(create_context, instance):
            return []

        attributes: list[AbstractAttrDef] = [
            TextDef(
                "frames_to_fix",
                label="Frames to fix",
                placeholder="5,10-15",
                regex="[0-9,-]+",
            ),
        ]

        if cls.rewrite_version_enable:
            attributes.append(
                BoolDef(
                    "rewrite_version",
                    label="Rewrite latest version",
                    default=False
                )
            )

        return attributes

    @classmethod
    def handle_backwards_compatibility(
        cls,
        create_context: CreateContext,
        instance: CreatedInstance,
    ) -> bool:
        """Handle compatibility with core's 'CollectFramesFixDef' plugin.

        There are 3 possible scenarios:
        1. This plugin was already used on an instance and stored values into
            instance.publish_attributes. In that case this plugin is used.
        2. This plugin was not used, and core's plugin is available and
            returns attribute definitions. In this case, this plugin should
            not be used to keep backwards compatibility -> do not show the
            same attributes twice.
        3. This plugin was not used, and core's plugin is not available
            or does not return attribute definitions. In this case,
            this plugin should be used and old values from core's plugin
            should be converted to this plugin's values.

        Stept to remove backwards compatibility:
        - [ ] Remove core plugin search and usage -> will require bump of core
            addon compatibility in 'package.py'.
        - [ ] Remove conversion of old values -> this is NOT related to addon
            versions, but to workfiles. This might stay here for a long time.

        Returns:
            bool: True if this plugin should be used, False if core's plugin
                should be used.

        """
        # If there is 'CollectFramesFixDef' plugin in context and returns
        #   definitions, do not show this plugin that means old ayon-core
        #   is used.
        # In case this plugin already did store values then use it anyways.
        # - that can happen if studio downgraded to old core.
        # TODO bump required 'core' version to package.py when removing
        #   search for core addon
        core_plugin_name = "CollectFramesFixDef"
        # Cache core plugin to avoid searching it on each instance.
        core_plugin = cls.core_plugin
        if core_plugin is NOT_SET:
            core_plugin = None
            for plugin in create_context.plugins_with_defs:
                if plugin.__class__.__name__ == core_plugin_name:
                    core_plugin = plugin
                    break
            cls.core_plugin = core_plugin

        if core_plugin is None:
            # Make sure old values are not stored in instance
            instance.publish_attributes.pop(core_plugin_name, None)
            return True

        # This plugin was already used -> use this plugin values
        # - we could monkey patch the core plugin to use this plugin values
        #   but the order in which this method is called is not deterministic.
        if cls.__name__ in instance.publish_attributes:
            return True

        # Core does not have the plugin anymore
        if core_plugin is not None:
            # Core has the plugin, if it returns attribute definitions,
            #   do not show this plugin, because it means old core is used.
            attrs = core_plugin.get_attr_defs_for_instance(
                create_context, instance
            )
            if attrs:
                return False

        # Convert old values to new plugin values and store them into instance
        old_values = {}
        if core_plugin_name in instance.publish_attributes:
            # Remove the values if core addon is not available
            if core_plugin is None:
                old_values = instance.publish_attributes.pop(
                    core_plugin_name
                )
            else:
                old_values = instance.publish_attributes[core_plugin_name]

        new_values = {
            key: value
            for key, value in (
                ("frames_to_fix", old_values.get("frames_to_fix")),
                ("rewrite_version", old_values.get("rewrite_version")),
            )
            if value is not None
        }
        instance.publish_attributes[cls.__name__] = new_values

        return True