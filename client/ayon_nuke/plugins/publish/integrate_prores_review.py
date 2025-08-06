import pyblish.api
from file_sequence import SequenceFactory
from ayon_core.pipeline.publish import OptionalPyblishPluginMixin
from pathlib import Path
from importlib import reload
import nuke
import json
import os
import copy

import hornet_publish_review_media

reload(hornet_publish_review_media)

import inspect


def get_frame_padded(frame, padding):
    """Return frame number as string with `padding` amount of padded zeros"""
    return "{frame:0{padding}d}".format(padding=padding, frame=frame)


# class IntegrateProresReview(publish.Integrator, OptionalPyblishPluginMixin):
class IntegrateProresReview(
    pyblish.api.InstancePlugin, OptionalPyblishPluginMixin
):
    """Generate ProRes review files using Nuke templates.

    Creates ProRes files directly from rendered frames without AYON registration.
    Calls hornet_publish_review_media.hornet_review_media_submit or
    hornet_publish_review_media.generate_review_media_local
    to generate the review media

    See that module for more info
    """

    label = "Integrate ProRes Review"
    order = pyblish.api.IntegratorOrder + 4.1
    families = ["render", "prerender"]
    hosts = ["nuke"]

    settings_category = "nuke"

    optional = True  # This makes the plugin optional in the UI

    def process(self, instance):
        # Skip review generation for prerenders
        product_type = instance.data.get("productType")
        if product_type == "prerender":
            self.log.info("Skipping review generation for prerender instance")
            return

        project_settings = instance.context.data["project_settings"]
        nuke_settings = project_settings.get("nuke", {})
        publish_settings = nuke_settings.get("publish", {})

        # get template script from web ui ----------------------------
        try:
            plugin_settings = publish_settings["HornetReviewMedia"]
        except KeyError:
            raise Exception("HornetReviewMedia settings not found, failing")

        try:
            template_script = plugin_settings["template_script"]
        except KeyError:
            raise Exception("template_script not found, failing")

        if not Path(template_script).exists():
            raise Exception(
                f"template script {template_script} does not exist, failing"
            )

        self.log.info(f"Template script: {template_script}")

        # get use farm toggle from publish dialog --------------------

        try:
            review_use_farm = instance.data["creator_attributes"][
                "hornet_review_use_farm"
            ]
        except KeyError:
            raise Exception("hornet_review_use_farm not found, failing")

        # ------------------------------------------------------------

        render_target = instance.data.get("render_target")
        self.log.info(f"render_target: {render_target}")

        # id to set dependency if we're integratingt he actual render on the farm
        # otherwise it will attempt to generate review media from nonexistent publish
        # Only needed for farm workflows (frames_farm), not local workflows (frames)
        deadline_job_id = None
        job_type = None

        if (
            render_target == "frames_farm"
        ):  # frames farm means the render is integrated on the farm
            render_job_id = instance.data.get("deadlineSubmissionJob", {}).get(
                "_id"
            )
            publish_job_id = self._get_deadline_publish_job_id(instance)
            deadline_job_id = render_job_id or publish_job_id

            if deadline_job_id is None:
                self.log.warning(
                    "failed to get deadline job id for frames_farm workflow"
                )
                return

            job_type = "render" if render_job_id else "publish"
            self.log.info(f"deadline {job_type} job id: {deadline_job_id}")
        else:  # otherwise we are set to "frames" which means the integration has already happened
            self.log.info(
                "Local rendering workflow - no deadline job dependency needed"
            )

        job_batch_name = instance.data.get("jobBatchName")
        current_file = instance.context.data.get("currentFile")
        path = instance.data.get("path", None)

        if path is None:
            raise Exception("failed to get publish path")

        review_enabled = (
            creator_attributes := instance.data.get("creator_attributes")
        ) and creator_attributes.get("review")

        if not review_enabled:
            self.log.info("review is not enabled, skipping")
            return

        try:
            review_burnin = instance.data["creator_attributes"][
                "review_burnin"
            ]
        except KeyError:
            review_burnin = True
            self.log.warning(
                "review_burnin not found in creator attributes, defaulting to True"
            )

        fps = nuke.toNode("root")["fps"].getValue()
        publish_dir = instance.data.get("publishDir", None)
        version = instance.data.get("version", None)
        write_node = instance.data["transientData"].get("writeNode")
        fs = SequenceFactory.from_nuke_node(write_node)
        name = instance.data.get("name", None)
        ext = instance.data.get("ext", None)
        colorspace = instance.data.get("colorspace", None)
        framestart = instance.data["frameStart"]
        frameend = instance.data["frameEnd"]

        shot = (
            anatomy_data := instance.data.get("anatomyData")
        ) and anatomy_data.get("asset")

        version = (
            anatomy_data := instance.data.get("anatomyData")
        ) and anatomy_data.get("version")

        project = (
            project_data := instance.data.get("project")
        ) and project_data.get("name")

        self.log.info(f"fps: {fps}")

        if publish_dir is None:
            self.log.warning("failed to get publish dir")
            return
        self.log.info(f"publish_dir: {publish_dir}")

        if version is None:
            self.log.warning("failed to get version")
            return
        self.log.info(f"version: {version}")

        if write_node is None:
            self.log.warning("failed to get write node")
            return

        self.log.info(f"write_node: {write_node.name()}")

        if fs is None:
            self.log.warning("failed to get file sequence")
            raise Exception("failed to get file sequence, failing")
        self.log.debug(f"file sequence: {fs}")

        if name is None:
            self.log.warning("failed to get name")
            raise Exception("failed to get name, failing")

        if ext is None:
            self.log.warning("failed to get ext")
            raise Exception("failed to get ext, failing")

        if shot is None:
            self.log.warning("failed to get shot")
            raise Exception("failed to get shot, failing")

        if version is None:
            self.log.warning("failed to get version")
            raise Exception("failed to get version, failing")

        if project is None:
            self.log.warning("failed to get project")
            raise Exception("failed to get project, failing")

        self.log.info(f"colorspace: {colorspace}")
        self.log.info(f"shot: {shot}")
        self.log.info(f"name: {name}")
        self.log.info(f"ext: {ext}")
        self.log.info(f"project: {project}")
        self.log.info(f"version: {version}")
        self.log.info(f"review_burnin: {review_burnin}")

        """
        File Sequence
        
        Use a FileSequence of the published files to help the hornet_publish_review_media
        prepare its data

        If the publish has already happened, we can use that to get the file sequence since it's
        foolproof 

        If it is a farm publish we have to construct the future file path / names from the anatomy
        and create a virtual file sequencw
        """

        published_sequences = SequenceFactory.from_directory(Path(publish_dir))

        if not published_sequences:
            self.log.info(
                "no sequences found in publish directory, normal if farm publishing"
            )
            self.log.info("using anatomy to construct file sequence")

            repz = instance.data.get("representations", [])

            for rep in repz:
                if rep["ext"] != ext:
                    continue

                self.log.debug(f"published_path: {rep['published_path']}")

                anatomy = instance.context.data["anatomy"]
                template_data = copy.deepcopy(instance.data["anatomyData"])
                template_data["representation"] = rep["name"]
                template_data["ext"] = rep["ext"]
                publish_template = anatomy.get_template_item(
                    "publish", "render"
                )

                path_template_obj = publish_template["path"]
                frame_padding = anatomy.templates_obj.frame_padding
                framez = []

                for frame in range(framestart, frameend + 1):
                    frame_template_data = template_data.copy()
                    frame_template_data["frame"] = frame

                    template_filled = path_template_obj.format_strict(
                        frame_template_data
                    )
                    framez.append(os.path.basename(str(template_filled)))

                self.log.debug(
                    f"Built frame sequence using anatomy templates with {frame_padding} digit padding"
                )
                self.log.debug(f"Template: {path_template_obj.template}")
                self.log.debug(
                    f"Sample frame files: {framez[:3]}{'...' if len(framez) > 3 else ''}"
                )

                published_sequences = SequenceFactory.from_filenames(
                    filenames=framez,
                    directory=publish_dir,
                )
                break

        if not published_sequences:
            self.log.warning(
                "no sequences found in instance data file list, failing"
            )
            raise Exception("no sequences found, failing")

        if len(published_sequences) > 1:
            self.log.warning(
                "multiple sequences found in publish directory, that shouldn't really happen. Using first"
            )

        published_sequence = published_sequences[0]

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

        # Data to pass to the render script

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
            "colorspace": colorspace,
            "burnin": review_burnin,
            "fps": fps,
            "deadline_job_id": deadline_job_id,
            "job_type": job_type,
            "render_target": render_target,
            "jobBatchName": job_batch_name,
            "currentFile": current_file,
        }

        self.log.debug(f"data: {data}")

        self.log.debug(
            inspect.getfile(
                hornet_publish_review_media.hornet_review_media_submit
            )
        )

        # if we are using the farm, we need to submit the review media to the farm

        if review_use_farm == False and render_target == "frames_farm":
            review_use_farm = True
            self.log.debug("forcing review_use_farm to True")

        try:
            if review_use_farm:
                success = (
                    hornet_publish_review_media.hornet_review_media_submit(
                        data, logger=self.log
                    )
                )
                if not success:
                    self.log.warning(
                        "Failed to submit ProRes review to farm. "
                        "Main publish will continue without review media."
                    )
                    return
            else:
                hornet_publish_review_media.generate_review_media_local(
                    data, logger=self.log
                )

            self.log.info(
                "ProRes review media generation completed successfully"
            )

        except Exception as e:
            self.log.warning(
                f"ProRes review media generation failed: {e}. "
                "Main publish will continue without review media."
            )
            return

    def _get_deadline_publish_job_id(self, instance):
        """
        The submit_publish_job.py plugin writes the job ID to a metadata JSON file.
        """
        try:
            ins_data = instance.data
            output_dir = ins_data.get(
                "publishRenderMetadataFolder", ins_data.get("outputDir")
            )

            if not output_dir:
                self.log.debug("No output directory found for metadata file")
                return None

            metadata_filename = f"{ins_data['productName']}_metadata.json"
            metadata_path = os.path.join(output_dir, metadata_filename)

            if not os.path.exists(metadata_path):
                self.log.debug(f"Metadata file not found: {metadata_path}")
                return None

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            publish_job_id = metadata.get("deadline_publish_job_id")
            if publish_job_id:
                self.log.debug(
                    f"Found deadline publish job ID in metadata: {publish_job_id}"
                )
            else:
                self.log.debug(
                    "No deadline_publish_job_id found in metadata file"
                )

            return publish_job_id

        except Exception as e:
            self.log.debug(
                f"Failed to read deadline publish job ID from metadata: {e}"
            )
            return None
