from __future__ import annotations

import pyblish.api
from typing import Any
import nuke
from ayon_nuke import api as napi


class CollectBurninMetadata(pyblish.api.InstancePlugin):
    """Collect Nuke metadata stream values as burnin/slate formatting keys.

    Metadata is read from the stream entering the instance's Write node
    (e.g. keys added upstream by a ModifyMetaData node such as
    `camera/focal` with an expression `[value Camera1.focal]`).

    Each configured entry is either an exact metadata key or a prefix
    ending with "/" (e.g. "camera/" collects every "camera/*" key).
    Collected keys are exposed unchanged, so `{camera/focal}` can be used
    in burnin templates and `{custom[camera/focal]}` in slate templates.
    """

    order = pyblish.api.CollectorOrder + 0.3
    label = "Collect Burnin Metadata"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]

    settings_category = "nuke"

    metadata_keys = ["camera/"]

    # Characters that would break `str.format` field names
    _invalid_key_chars = set("{}:[].!")

    def process(self, instance):
        if not self.metadata_keys:
            self.log.debug("No metadata keys configured. Skipping.")
            return

        write_node = self._get_write_node(instance)
        if write_node is None:
            self.log.debug(
                "No Write node found for instance '{}'. Skipping burnin "
                "metadata collection.".format(instance.data["name"])
            )
            return

        frame = instance.data.get(
            "frameStartHandle", instance.data.get("frameStart")
        )

        metadata = write_node.metadata(time=frame) or {}
        if metadata is None:
            self.log.debug(
                f"Failed to read metadata from '{write_node.fullName()}'."
            )
            return

        collected = {}
        for key, value in metadata.items():
            if not self._is_requested(key):
                continue
            if self._invalid_key_chars.intersection(key):
                self.log.debug(
                    f"Metadata key '{key}' contains characters not usable in "
                    "templates. Skipping."
                )
                continue
            collected[key] = self._normalize_value(value)

        missing = [
            key for key in self.metadata_keys
            if not key.endswith("/") and key not in collected
        ]
        if missing:
            self.log.debug(
                f"Metadata keys not found on '{write_node.fullName()}'"
                f" at frame {frame}: {', '.join(missing)}"
            )

        if not collected:
            return

        instance.data.setdefault("burninDataMembers", {}).update(collected)

        self.log.debug("Collected burnin metadata: {}".format(collected))

    def _get_write_node(self, instance: pyblish.api.Instance) -> nuke.Node:
        """Get the Write node associated with the instance.

        Args:
            instance (pyblish.api.Instance): The instance to get the Write
                node for.

        Returns:
            nuke.Node: The associated Write node, or None if not found.
        """
        write_node = instance.data["transientData"].get("writeNode")
        if write_node is not None:
            return write_node

        for node in napi.get_instance_group_node_children(instance):
            if node.Class() == "Write":
                return node
        return None

    def _is_requested(self, key: str) -> bool:
        """Check if the metadata key is requested.

        Args:
            key (str): The metadata key to check.

        Returns:
            bool: True if the key is requested, False otherwise.
        """
        for requested in self.metadata_keys:
            if requested.endswith("/"):
                if key.startswith(requested):
                    return True
            elif key == requested:
                return True
        return False

    @staticmethod
    def _normalize_value(
        value: Any) -> str | int | bool | float | None:
        """Normalize the value to a string, integer, boolean, or float.

        Args:
            value (Any): The value to normalize.

        Returns:
            str | int | bool | float | None: The normalized
                string value, integer, boolean, float, or None.
        """
        if isinstance(value, (bool, int, float, str)) or value is None:
            return value
        return str(value)
