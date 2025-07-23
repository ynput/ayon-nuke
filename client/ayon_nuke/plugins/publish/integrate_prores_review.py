from math import e
import pyblish.api
import hornet_publish
from file_sequence import SequenceFactory

from ayon_core.pipeline.publish import OptionalPyblishPluginMixin
from pathlib import Path


# class IntegrateProresReview(publish.Integrator, OptionalPyblishPluginMixin):
class IntegrateProresReview(
    pyblish.api.InstancePlugin, OptionalPyblishPluginMixin
):
    """Generate ProRes review files using Nuke templates.

    Creates ProRes files directly from rendered frames without AYON registration.
    Runs only locally - ProRes files are created during local publish and then
    transferred during farm publishing.
    """

    label = "Integrate ProRes Review"
    order = pyblish.api.ExtractorOrder + 4.1
    families = ["render", "prerender"]
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, instance):
        self.log.info("integrate_prores_review")


        project_settings = instance.context.data["project_settings"]
        nuke_settings = project_settings.get("nuke", {})
        publish_settings = nuke_settings.get("publish", {})

        

        # get template script from web ui
        try:
            plugin_settings = publish_settings["HornetReviewMedia"]
        except KeyError:
            raise Exception("HornetReviewMedia settings not found, failing")
        
        try:
            template_script = plugin_settings["template_script"]
        except KeyError:
            raise Exception("template_script not found, failing")
        
        if not Path(template_script).exists():
            raise Exception(f"template script {template_script} does not exist, failing")

        self.log.info(f"Template script: {template_script}")


        # get use farm toggle from publish dialog 
        try:
            use_farm = instance.data["creator_attributes"]["hornet_review_use_farm"]
        except KeyError:
            raise Exception("hornet_review_use_farm not found, failing")
        
        self.log.info(f"Use farm: {use_farm}")
        
        
        
        # get other data
        path = instance.data.get("path", None)

        if path is None:
            raise Exception("failed to get publish path")

        review_enabled = (
            creator_attributes := instance.data.get("creator_attributes")
        ) and creator_attributes.get("review")

        if not review_enabled:
            self.log.info("review is not enabled, skipping")
            return

        publish_dir = instance.data.get("publishDir", None)
        if publish_dir is None:
            self.log.warning("failed to get publish dir")
            return
        self.log.info(f"publish_dir: {publish_dir}")

        version = instance.data.get("version", None)
        if version is None:
            self.log.warning("failed to get version")
            return
        self.log.info(f"version: {version}")

        write_node = instance.data["transientData"].get("writeNode")
        if write_node is None:
            self.log.warning("failed to get write node")
            return

        self.log.info(f"write_node: {write_node.name()}")

        fs = SequenceFactory.from_nuke_node(write_node)
        if fs is None:
            self.log.warning("failed to get file sequence")
            raise Exception("failed to get file sequence, failing")
        self.log.debug(f"file sequence: {fs}")

        name = instance.data.get("name", None)
        if name is None:
            self.log.warning("failed to get name")
            raise Exception("failed to get name, failing")

        ext = instance.data.get("ext", None)
        if ext is None:
            self.log.warning("failed to get ext")
            raise Exception("failed to get ext, failing")

        # shot = instance.data.get("anatomyData", None).get("asset", None)
        shot = (
            anatomy_data := instance.data.get("anatomyData")
        ) and anatomy_data.get("asset")

        if shot is None:
            self.log.warning("failed to get shot")
            raise Exception("failed to get shot, failing")

        version = (
            anatomy_data := instance.data.get("anatomyData")
        ) and anatomy_data.get("version")
        if version is None:
            self.log.warning("failed to get version")
            raise Exception("failed to get version, failing")

        project = (
            project_data := instance.data.get("project")
        ) and project_data.get("name")
        if project is None:
            self.log.warning("failed to get project")
            raise Exception("failed to get project, failing")

        self.log.info(f"shot: {shot}")
        self.log.info(f"name: {name}")
        self.log.info(f"ext: {ext}")
        self.log.info(f"project: {project}")
        self.log.info(f"version: {version}")


        published_sequences = SequenceFactory.from_directory(Path(publish_dir))
        if not published_sequences:
            self.log.warning("no sequences found in publish directory")
            return

        if len(published_sequences) > 1:
            self.log.warning(
                "multiple sequences found in publish directory, that shouldn't really happen. Using first"
            )
        published_sequence = published_sequences[0]

        # TODO build the expected sequence name from the template and search for that

        self.log.info(
            f"published sequence absolute file name: {published_sequence.absolute_file_name}"
        )
        self.log.info(
            f"published sequence sequence string: {published_sequence.sequence_string()}"
        )
        self.log.info(
            f"published sequence first frame: {published_sequence.first_frame}"
        )
        self.log.info(
            f"published sequence last frame: {published_sequence.last_frame}"
        )

        # return

        data = {
            "publishDir": publish_dir,
            "version": version,
            "writeNode": write_node.fullName(),
            "publishedSequence": published_sequence.absolute_file_name,
            "first_frame": published_sequence.first_frame,
            "last_frame": published_sequence.last_frame,
            "name": name,
            "shot": shot,
            "project": project,
            "template_script": template_script,
        }

        self.log.debug(f"data: {data}")

        # submit to deadline or generate review media locally
        if use_farm:
            if hornet_publish.hornet_review_media_submit(
                data, logger=self.log
            ):
                self.log.info("submitted to deadline")
            else:
                self.log.warning("failed to submit to deadline")
        else:
            hornet_publish.generate_review_media_local(data, logger=self.log)
            self.log.warning("failed to submit to deadline")
