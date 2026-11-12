import logging

from qtpy import QtWidgets
from scriptsmenu import scriptsmenu


log = logging.getLogger(__name__)


def _nuke_main_window():
    """Return Nuke's main window"""
    for obj in QtWidgets.QApplication.topLevelWidgets():
        if (
            obj.inherits("QMainWindow")
            and obj.metaObject().className() == "Foundry::UI::DockMainWindow"
        ):
            return obj
    raise RuntimeError("Could not find Nuke MainWindow instance")


def _nuke_main_menubar():
    """Retrieve Nuke's existing main menubar without creating a new one

    `QMainWindow.menuBar()` creates and installs an empty menubar when the
    window has none. On macOS, Nuke's menus live in a native menubar shared
    by all windows (a `QMenuBar` without a parent), so the main window has no
    menubar of its own, and the empty one `menuBar()` creates replaces Nuke's
    menus in the macOS menubar. `menuWidget()` returns the window's menubar
    or None and never creates one.
    """
    nuke_window = _nuke_main_window()

    menubar = nuke_window.menuWidget()
    if isinstance(menubar, QtWidgets.QMenuBar):
        return menubar

    # macOS: the shared menubar is a top level widget, prefer one with menus
    shared_menubars = [
        widget
        for widget in QtWidgets.QApplication.topLevelWidgets()
        if isinstance(widget, QtWidgets.QMenuBar)
    ]
    for menubar in shared_menubars:
        if menubar.actions():
            return menubar
    if shared_menubars:
        return shared_menubars[0]

    log.warning(
        "Could not find Nuke's menubar, creating a new one for the"
        " scripts menu."
    )
    return nuke_window.menuBar()


def main(title="Scripts"):
    nuke_main_bar = _nuke_main_menubar()
    for nuke_bar in nuke_main_bar.children():
        if isinstance(nuke_bar, scriptsmenu.ScriptsMenu):
            if nuke_bar.title() == title:
                menu = nuke_bar
                return menu

    menu = scriptsmenu.ScriptsMenu(title=title, parent=nuke_main_bar)
    return menu
