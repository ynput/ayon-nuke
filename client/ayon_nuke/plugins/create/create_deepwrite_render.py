from ayon_nuke.plugins.create.create_write_render import CreateWriteRender


class CreateDeepWriteRender(CreateWriteRender):
    settings_category = "nuke"

    identifier = "create_deepwrite_render"
    label = "Render (deep write)"
    product_base_type = "render"
    product_type = product_base_type
    icon = "sign-out"
    node_class = "DeepWrite"

    instance_attributes = []
    default_variants = ["DeepMain"]

