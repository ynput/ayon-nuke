import nuke
import nukescripts
from pathlib import Path
from datetime import datetime
from PySide2.QtCore import QTimer

NODE_LOCATION = Path(r"P:\dev\alexh_dev\jesseSend")

"""
This system allows users to copy a kind of URL associated with a scriptlet, and paste
it into a chat window, allowing the other user to paste the url directly into the nuke
node graph and a callback will intercept and paste the scriptlet

it's very convenient

stolen from Jesse Spielman
"""


def pasteDropNode(path):
    
    results = nuke.nodePaste(path)


def jesse_send():
    
    time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    script_name = Path(nuke.root().name()).stem
    file_name = f"{script_name}_{time_stamp}.nk"
    path = NODE_LOCATION / file_name
    nuke.nodeCopy(str(path))  
    jesse_url = "JESSE::" + str(path) 
    nuke.message(jesse_url)

    return jesse_url


def handle_jesse_send(type, data):

    print("handling drop")

    if type != "text/plain":
        print("not text/plain")
        return None
    
    if not data.lstrip().startswith("JESSE::"):
        print("not JESSE::")
        return None

    print("Jesse drop detected!")

    path = Path(data.lstrip().replace("JESSE::", ""))

    if not Path(path).exists():
        print("File not found")
        return True

    spath = path.as_posix()
    try:
        QTimer.singleShot(0, lambda: pasteDropNode(spath))
    except Exception as e:
        print(f"exception: {e}")
    
    return True


nukescripts.drop.addDropDataCallback(handle_jesse_send)
nuke.toolbar("Nodes").addCommand("Alex Dev / Jesse Send", "jesse_send()")


# JESSE::P:\dev\alexh_dev\jesseSend\Root_2025-02-10_12-04-18.nkz