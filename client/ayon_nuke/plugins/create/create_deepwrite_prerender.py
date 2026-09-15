from ayon_nuke.plugins.create.create_write_prerender import (
    CreateWritePrerender,
)


class CreateDeepWritePrerender(CreateWritePrerender):
    settings_category = "nuke"

    identifier = "create_deepwrite_prerender"
    label = "Prerender (deep write)"
    product_base_type = "prerender"
    product_type = product_base_type
    icon = "sign-out"
    node_class = "DeepWrite"

    instance_attributes = ["use_range_limit"]
    default_variants = ["DeepMain"]

    # Before write node render.
    order = 90

