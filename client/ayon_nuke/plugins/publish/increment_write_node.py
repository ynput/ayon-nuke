# -*- coding: utf-8 -*-
"""Increments render path in write node with actual workfile version"""
import pyblish.api
from ayon_core.pipeline import OptionalPyblishPluginMixin

from ayon_nuke.api.lib import writes_version_sync


class IncrementWriteNodePath(pyblish.api.InstancePlugin,
                             OptionalPyblishPluginMixin):
    """Increments render path in write node with actual workfile version

    This allows to send multiple publishes to DL (for all of them Publish part
    suspended) that wouldn't overwrite `renders` subfolders.

    Ignores artist hardcoded paths and `frames`, eg `Use existing frames` where
    path should stay put.

    """

    order = pyblish.api.IntegratorOrder + 10
    label = "Increment path in Write node"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"
    optional = True
    active = True

    def process(self, instance):
        if not instance.data.get("stagingDir_is_custom"):
            self.log.info(
                f"'{instance}' instance doesn't have custom staging dir."
            )
            return

        write_node = instance.data["transientData"].get("writeNode")
        if write_node is None:
            group_node = instance.data["transientData"]["node"]
            self.log.info(
                f"Instance '{group_node.name()}' is missing write node!"
            )
            return

        render_target = instance.data["render_target"]
        if render_target in ["frames", "frames_farm"]:
            self.log.info("Instance reuses existing frames, not updating path")
            return

        writes_version_sync(write_node, self.log)
