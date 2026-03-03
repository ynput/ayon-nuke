from ayon_core.pipeline import registered_host


# This code gets only called from GUI mode.
# Unlike the farm, we do exepct a valid registered host at this time.
nuke_host = registered_host()
if nuke_host is None:
    raise RuntimeError("Cannot find expected registered Nuke host.")

nuke_host.setup_ui_callbacks_and_menu()
