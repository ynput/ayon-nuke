import os


ASSIST = bool(os.getenv("NUKEASSIST"))
LOADER_CATEGORY_COLORS = {
    "latest": "0x4ecd25ff",
    "outdated": "0xd84f20ff",
    "invalid": "0xff0000ff",
    "not_found": "0xffff00ff",
}

COLOR_VALUE_SEPARATOR = ";"
