from ayon_nuke.plugins.create.create_write_prerender import (
    CreateWritePrerender,
)


class CreateDeepWritePrerender(CreateWritePrerender):
    settings_category = "nuke"

    identifier = "create_deepwrite_prerender"
    label = "Prerender (deep write)"
    node_class = "DeepWrite"
    default_variants = ["DeepMain"]


