from __future__ import annotations

import pyblish.api
from typing import Any
import nuke
from ayon_nuke import api as napi
from ayon_core.pipeline import OptionalPyblishPluginMixin

#: Characters that are not allowed in `str.format` field names, and thus
#: cannot be used in burnin/slate template keys like `{camera/focal}`.
INVALID_METADATA_KEY_CHARS = frozenset("{}:[].!")


class CollectBurninMetadata(pyblish.api.InstancePlugin,
                            OptionalPyblishPluginMixin):
    """Collect Nuke metadata stream values as burnin formatting keys.

    Metadata is read from the stream entering the instance's Write node
    (e.g. keys added upstream by a ModifyMetaData node such as
    `camera/focal` with an expression `[value Camera1.focal]`).

    Each configured entry is either an exact metadata key or a prefix
    ending with "/" (e.g. "camera/" collects every "camera/*" key).
    Collected keys are exposed unchanged, so they can be used in burnin
    templates, e.g. `{camera/focal}`.

    Metadata is sampled for every frame of the instance's handled range.
    Keys whose values differ between frames are stored as a list with one
    value per frame, in frame order (the same semantics as the Maya and
    Houdini collectors' animated focal length). Constant keys are stored
    as a single value.
    """

    order = pyblish.api.CollectorOrder + 0.3
    label = "Collect Burnin Metadata"
    hosts = ["nuke", "nukeassist"]
    families = ["render", "prerender", "image"]
    optional = True
    settings_category = "nuke"

    # Settings are applied automatically by AYON's plugin discovery using
    # `settings_category` and the plugin class name, so no extra mixin is
    # needed to load `metadata_keys` (or `enabled`) from the addon settings.
    metadata_keys = ["camera/"]

    def process(self, instance):
        if not self.is_active(instance.data):
            return

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

        # CollectWrites adds the handled frame range to every write instance
        frame_start = int(instance.data["frameStartHandle"])
        frame_end = int(instance.data["frameEndHandle"])
        frame_ranges = range(frame_start, frame_end + 1)
        sample_frames = list(frame_ranges)

        values_by_frame = {
            frame: self._get_requested_metadata(write_node, frame)
            for frame in sorted(sample_frames)
        }

        collected = {}
        all_frame_keys = sorted({
            key
            for values in values_by_frame.values()
            for key in values
        })
        for key in all_frame_keys:
            values = [
                metadata.get(key)
                for metadata in values_by_frame.values()
            ]
            # Keep one value per frame so burnin lists stay aligned with the
            # rendered frames. A key missing on a frame is an empty value.
            if not any(values):
                continue
            values = ["" if value is None else value for value in values]
            first_value = repr(values[0])
            if all(repr(value) == first_value for value in values):
                # Constant key: a single value keeps the burnin static.
                collected[key] = values[0]
            else:
                # Animated key: one value per frame for the burnin script.
                collected[key] = values

        missing = {
            key for key in self.metadata_keys
            if not key.endswith("/") and key not in collected
        }
        if missing:
            self.log.debug(
                f"Metadata keys not found on '{write_node.fullName()}'"
                f" at frames {frame_start}-{frame_end}: "
                f"{', '.join(sorted(missing))}"
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

    def _get_requested_metadata(
        self, write_node: nuke.Node, frame: int
    ) -> dict[str, str | int | bool | float | None]:
        """Read the requested metadata entering the Write node at a frame.

        Args:
            write_node (nuke.Node): The Write node to read metadata from.
            frame (int): The frame to evaluate the metadata at.

        Returns:
            dict[str, str | int | bool | float | None]: Requested metadata
                keys with normalized values.
        """
        metadata = write_node.metadata(time=frame)
        if not metadata:
            return {}
        return {
            key: self._normalize_value(value)
            for key, value in metadata.items()
            if self._is_requested(key)
        }

    def _is_requested(self, key: str) -> bool:
        """Check if the metadata key is requested.

        Metadata keys containing characters that cannot be used in
        `str.format` field names are ignored, because the collected keys
        are referenced by burnin/slate templates as format fields, e.g.
        `{camera/focal}`. Such keys could never be used in a template.
        The same restriction is enforced for the configured keys by the
        addon settings model.

        Args:
            key (str): The metadata key to check.

        Returns:
            bool: True if the key is requested, False otherwise.
        """
        if any(char in key for char in INVALID_METADATA_KEY_CHARS):
            return False

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
