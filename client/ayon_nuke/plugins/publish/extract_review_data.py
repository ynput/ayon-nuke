import os
from pprint import pformat
import pyblish.api

from ayon_core.pipeline import publish

from ayon_nuke.api import traits as nuke_traits


class ExtractReviewData(publish.Extractor):
    """Extracts review tag into available representation
    """

    order = pyblish.api.ExtractorOrder + 0.01
    # order = pyblish.api.CollectorOrder + 0.499
    label = "Extract Review Data"

    families = ["review"]
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, instance):
        fpath = instance.data["path"]
        ext = os.path.splitext(fpath)[-1][1:]

        representations = instance.data.get("representations", [])

        # review can be removed since `ProcessSubmittedJobOnFarm` will create
        # reviewable representation if needed
        if (
            instance.data.get("farm")
            and "review" in instance.data["families"]
        ):
            instance.data["families"].remove("review")

        if nuke_traits.uses_trait_representations(instance):
            for representation in publish.get_trait_representations(
                instance
            ):
                filenames = nuke_traits.get_representation_filenames(
                    representation)
                if not filenames or not filenames[0].endswith(f".{ext}"):
                    continue
                nuke_traits.add_tag(representation, "review")
                self.log.debug(
                    f"Matching trait representation: {representation.name}"
                )
            return

        # iterate representations and add `review` tag
        for repre in representations:
            if ext != repre["ext"]:
                continue

            if not repre.get("tags"):
                repre["tags"] = []

            if "review" not in repre["tags"]:
                repre["tags"].append("review")

            self.log.debug("Matching representation: {}".format(
                pformat(repre)
            ))

        instance.data["representations"] = representations
