import nuke

class ValidateRenderFrameRange:
    """Validator to ensure render products inherit root frame range."""

    def process(self, instance):
        if instance.data.get("productType") == "render":
            root = nuke.root()
            if not root:
                return
            first = int(root["first_frame"].value())
            last = int(root["last_frame"].value())
            # If frame range is default (1-1), overwrite with root
            if instance.data.get("frameStart") == 1 and instance.data.get("frameEnd") == 1:
                instance.data["frameStart"] = first
                instance.data["frameEnd"] = last
                self.log.info(
                    "Updated render product %s frame range to script root: %d-%d",
                    instance.data["name"],
                    first,
                    last,
                )