"""Retime nodes `LoadClip` re-creates on update stay members of the read.

An update runs on a new loader instance, which never calls
`reset_container_id`. The re-created TimeWarp got an empty container id,
so the next update did not clear it (a second TimeWarp was added) and
Load Effects could not see that the read node has a retime.
"""

import nuke

from ayon_nuke.plugins.load.load_clip import LoadClip

VERSION_ATTRIBUTES = {"handleStart": 0, "frameStart": 1001, "frameEnd": 1010}
VERSION_DATA = {
    "speed": 1,
    "timewarps": [{"Class": "TimeWarp", "name": "TimeWarp1", "lookup": 1.0}],
}


def _loaded_read():
    read = nuke.nodes.Read()
    knob = nuke.String_Knob(LoadClip.container_id_knob)
    read.addKnob(knob)
    knob.setValue("read-container-id")
    return read


def _timewarp_container_ids():
    return [
        node[LoadClip.container_id_knob].value()
        for node in nuke.allNodes(filter="TimeWarp")
    ]


def test_update_retime_keeps_the_read_container_id():
    read = _loaded_read()

    LoadClip()._make_retimes(read, VERSION_ATTRIBUTES, VERSION_DATA)

    assert _timewarp_container_ids() == ["read-container-id"]


def test_second_update_replaces_the_retime():
    read = _loaded_read()

    LoadClip()._make_retimes(read, VERSION_ATTRIBUTES, VERSION_DATA)
    LoadClip()._make_retimes(read, VERSION_ATTRIBUTES, VERSION_DATA)

    assert _timewarp_container_ids() == ["read-container-id"]
