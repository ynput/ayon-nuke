from ayon_nuke.plugins.create.create_write_render import CreateWriteRender


class CreateDeepWriteRender(CreateWriteRender):
    settings_category = "nuke"

    identifier = "create_deepwrite_render"
    label = "Render (deep write)"
    node_class = "DeepWrite"
    default_variants = ["DeepMain"]

