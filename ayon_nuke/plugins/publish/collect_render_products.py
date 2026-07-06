# ayon_nuke/plugins/publish/collect_render_products.py
# Corrected version to fix frame range inheritance for render products

import nuke
import pyblish.api
from ayon_nuke.api import plugin
from ayon_nuke.lib import imprint


class CollectRenderProducts(plugin.NukeInstanceCollector):
    """Collect render products."""

    order = pyblish.api.CollectorOrder + 0.4
    label = "Collect Render Products"
    hosts = ["nuke"]

    def process(self, instance):
        # ... existing code ...
        # Ensure render products inherit frame range correctly
        # ...

    def _get_render_frame_range(self, product_data):
        """Get frame range for a render product.

        If product has a custom frame range set, parse and use it.
        If the custom frame range is missing, empty, or invalid,
        fall back to the script's root frame range.

        Args:
            product_data (dict): Product data containing optional 'frame_range' key.

        Returns:
            tuple[int, int]: First and last frame numbers.
        """
        custom_range = product_data.get("frame_range", "")
        if custom_range and isinstance(custom_range, str):
            parts = custom_range.split("-")
            if len(parts) == 2:
                try:
                    first = int(parts[0])
                    last = int(parts[1])
                    if first <= last:
                        return first, last
                except ValueError:
                    pass
        # Fall back to script root frame range
        root = nuke.root()
        first = int(root["first_frame"].value())
        last = int(root["last_frame"].value())
        return first, last

    # Other methods...
