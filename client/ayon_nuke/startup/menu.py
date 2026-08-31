from ayon_core.pipeline import registered_host


# This code gets only called from GUI mode.
# Unlike the non-GUI mode (e.g. farm),
# we do expect a valid host at this time.
nuke_host = registered_host()
if nuke_host is None:
    raise RuntimeError("Cannot find expected registered Nuke host.")

nuke_host.setup_ui_callbacks_and_menu()
if not nuke_host.get_current_workfile():
    from ayon_nuke.api.workfile_template_builder import trigger_on_app_launch
    trigger_on_app_launch()
nuke_host.app_initialized = True
