# -*- coding: utf-8 -*-
"""Increments render path in write node with actual workfile version"""

import nuke

import pyblish.api
from ayon_core.pipeline import OptionalPyblishPluginMixin

from ayon_nuke.api.lib import writes_version_sync


def _process_writes_sync(publish_item, instance):
    if not publish_item.is_active(instance.data):
        return

    if not instance.data.get("stagingDir_is_custom"):
        publish_item.log.info(
            f"'{instance}' instance doesn't have custom staging dir."
        )
        return

    write_node = instance.data["transientData"].get("writeNode")
    if write_node is None:
        group_node = instance.data["transientData"]["node"]
        publish_item.log.info(
            f"Instance '{group_node.name()}' is missing write node!"
        )
        return

    render_target = instance.data["render_target"]
    if render_target in ["frames", "frames_farm"]:
        publish_item.log.info(
            "Instance reuses existing frames, not updating path"
        )
        return

    writes_version_sync(write_node, publish_item.log)
    nuke.scriptSave()


class IncrementWriteNodePathPreSubmit(
    pyblish.api.InstancePlugin, OptionalPyblishPluginMixin
):
    """Increments render path in write node with actual workfile version
    before potential farm submission.

    This allows to send multiple publishes to DL (for all of them Publish part
    suspended) that wouldn't overwrite `renders` subfolders.

    Ignores artist hardcoded paths and `frames`, eg `Use existing frames` where
    path should stay put.

    """

    order = pyblish.api.IntegratorOrder
    label = "Update path in Write node - Pre Submit"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"
    optional = True
    active = True

    def process(self, instance):
        _process_writes_sync(self, instance)


class IncrementWriteNodePathPostSubmit(
    pyblish.api.InstancePlugin, OptionalPyblishPluginMixin
):
    """Increments render path in write node with actual workfile version after
    workfile has been incremented.

    This allows users to manually trigger a local render being sure
    the render output paths are updated.
    """

    order = pyblish.api.IntegratorOrder + 10
    label = "Update path in Write node - Post Version-Up"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"
    optional = True
    active = True

    def process(self, instance):
        _process_writes_sync(self, instance)