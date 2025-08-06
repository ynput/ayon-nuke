import nuke
import pyblish.api
import pyblish.util
from ayon_core.lib import Logger
from ayon_core.pipeline.create import CreateContext
from ayon_core.pipeline import registered_host
from ayon_core.tools.utils import show_message_dialog


def quick_publish(
    node,
    review=True,
    review_farm=True,
    integrate_farm=False,
    burnin=True,
    silent=False,
):
    """
    Submit a publish without using the ayon publish dialogue 

    Args:
        node (nuke.Node): The write group node 
        review (bool): Whether to generate review media
        review_farm (bool): Whether to generate review media on farm
        integrate_farm (bool): Whether to use farm integration ("frames_farm") or local ("frames")
        burnin (bool): Whether to include burnins in review media
        silent (bool): Suppress popup messages

    Returns:
        bool: True if successful, False if failed
    """

    # Ensure code is executed in root context
    # if nuke.root() != nuke.thisNode():
    #     with nuke.root():
    #         return manual_publish_write_node(
    #             node,
    #             review,
    #             review_farm,
    #             integrate_farm,
    #             burnin,
    #             silent,
    #         )

    log = Logger.get_logger(__name__)
    log.info(f"Starting quick publish for node: {node.fullName()}")

    if integrate_farm:
        if not review_farm:
            review_farm = True
            log.info("forcing review_farm to True because integrate_farm is True")

    try:
        host = registered_host() # gets current host - nuke in this case
        this_context = CreateContext(host) 

        # Find and activate only the specific instance we want to publish
        target_instance = None
        for instance in this_context.instances: #instances are publishable asstets ie renders
            if node.fullName() == instance.transient_data["node"].fullName(): # the write node
                instance.data["active"] = True
                target_instance = instance
                log.info(f"Activated instance: {instance}")
            else:
                instance.data["active"] = False

        if target_instance is None:
            raise Exception(f"No instance found for node: {node.name()}")

        # Set render target based on integrate_farm
        render_target = "frames_farm" if integrate_farm else "frames"
        target_instance.data["render_target"] = render_target
        log.info(f"Set render target to: {render_target}")

        # Also set render_target in creator_attributes to prevent override from publish dialogue
        # not sure if we need both
        try:
            target_instance.data["creator_attributes"]["render_target"] = (
                render_target
            )
            log.info(
                f"Set creator_attributes render_target to: {render_target}"
            )
        except Exception as e:
            log.warning(f"Could not set creator_attributes render_target: {e}")

        # Set farm flag to enable deadline job submission when needed
        target_instance.data["farm"] = integrate_farm
        log.info(f"Set farm flag to: {integrate_farm}")

        # Enable/disable review generation
        try:
            target_instance.data["creator_attributes"]["review"] = review
            log.info(f"Set review enabled: {review}")
        except Exception as e:
            log.warning(f"Could not set review setting: {e}")

        # farm or local for review
        try:
            target_instance.data["creator_attributes"][
                "hornet_review_use_farm"
            ] = review_farm
            farm_status = "farm" if review_farm else "local"
            log.info(f"Set review media generation to: {farm_status}")
        except Exception as e:
            log.warning(f"Could not set review farm setting: {e}")

        # Set review burnin setting
        try:
            target_instance.data["creator_attributes"]["review_burnin"] = (
                burnin
            )
            log.info(f"Set review burnin to: {burnin}")
        except Exception as e:
            log.warning(f"Could not set review burnin setting: {e}")

        # pyblish context is different from the create context
        # it is the execution context for the plugins
        context = pyblish.api.Context() 
        context.data["create_context"] = this_context
        context.data["node_name"] = node.name()

        # add project settings for integrate_prores_review.py to work
        try:
            from ayon_core.settings import get_current_project_settings

            project_settings = get_current_project_settings()
            context.data["project_settings"] = project_settings
            log.info("Added project settings to context")

        except Exception as e:
            log.warning(f"Could not get project settings: {e}")

        # get all publish plugins 
        plugins = pyblish.api.discover()
        log.info(
            f"Discovered {len(plugins)} plugins - following project settings"
        )

        # Ensure IntegrateProresReview plugin is included
        # prores_plugin = None
        # for plugin in plugins:
        #     if plugin.__name__ == "IntegrateProresReview":
        #         prores_plugin = plugin
        #         log.info("Found IntegrateProresReview plugin")
        #         break

        # if prores_plugin is None:
        #     log.warning(
        #         "IntegrateProresReview plugin not found - farm submission may not work"
        #     )

        # save script before publishing
        nuke.scriptSave()

        # run pyblish
        log.info("Running pyblish...")
        log.info(f"Running {len(plugins)} plugins")
        context = pyblish.util.publish(context, plugins=plugins)

        # did it work 
        error_message = ""
        success = True
        for result in context.data.get("results", []):
            if not result["success"]:
                success = False
                err = result["error"]

                
                plugin_name = "Unknown"
                if "plugin" in result:
                    plugin = result["plugin"]
                    if hasattr(plugin, "__name__"):
                        plugin_name = plugin.__name__

                # for validation errors log the actual error message
                if hasattr(err, "args") and err.args:
                    actual_error = (
                        str(err.args[0]) if err.args[0] else str(err)
                    )
                else:
                    actual_error = str(err)

                log.error(f"Plugin {plugin_name} failed: {actual_error}")
                error_message += f"\n{actual_error}"

        if not success:
            if not silent:
                show_message_dialog(
                    "Publish Errors",
                    f"Publish failed for {node.name()}:\n{error_message}",
                    level="critical",
                )
            return False
        else:
            log.info(f"Successfully published: {node.name()}")
            if not silent:
                show_message_dialog(
                    "Publish Successful",
                    f"Submitted {node.name()} for publish",
                )
            return True

    except Exception as e:
        error_msg = f"Failed to publish {node.name()}: {str(e)}"
        log.error(error_msg)
        show_message_dialog("Publish Error", error_msg, level="critical")
        return False


def batch_publish_write_nodes(
    write_nodes,
    delay_between_publishes=1.0,
    review=True,
    review_farm=True,
    integrate_farm=True,
    burnin=True,
    silent=True,
):
    """
    Publish multiple write nodes sequentially with delays to avoid memory issues

    Args:
        write_nodes (list): List of nuke write group nodes to publish
        delay_between_publishes (float): Seconds to wait between publishes
        review (bool): Whether to generate review media at all
        review_farm (bool): Whether to generate review media on farm (True) or locally (False)
        integrate_farm (bool): Whether to use farm integration ("frames_farm") or local ("frames")
        burnin (bool): Whether to include burnins in review media
        silent (bool): Suppress individual success/failure popup messages (batch summary still shown)

    Returns:
        dict: Results dictionary with success/failure counts and details
    """
    import time

    log = Logger.get_logger(__name__)
    results = {
        "total": len(write_nodes),
        "successful": [],
        "failed": [],
        "success_count": 0,
        "failure_count": 0,
    }

    log.info(f"Starting batch publish of {len(write_nodes)} write nodes")

    for i, node in enumerate(write_nodes):
        log.info(f"Publishing node {i + 1}/{len(write_nodes)}: {node.name()}")

        try:
            success = quick_publish(
                node,
                review=review,
                review_farm=review_farm,
                integrate_farm=integrate_farm,
                burnin=burnin,
                silent=silent,
            )

            if success:
                results["successful"].append(node.name())
                results["success_count"] += 1
                log.info(f"✓ Successfully published: {node.name()}")
            else:
                results["failed"].append(node.name())
                results["failure_count"] += 1
                log.error(f"✗ Failed to publish: {node.name()}")

        except Exception as e:
            results["failed"].append(node.name())
            results["failure_count"] += 1
            log.error(f"✗ Exception publishing {node.name()}: {str(e)}")

        # Add delay between publishes to prevent memory buildup
        if i < len(write_nodes) - 1:  # Don't delay after the last one
            log.info(
                f"Waiting {delay_between_publishes} seconds before next publish..."
            )
            time.sleep(delay_between_publishes)

    # Show summary
    summary = "Batch publish completed:\n"
    summary += f"Successful: {results['success_count']}/{results['total']}\n"
    summary += f"Failed: {results['failure_count']}/{results['total']}\n"

    if results["successful"]:
        summary += f"\nSuccessful nodes: {', '.join(results['successful'])}"
    if results["failed"]:
        summary += f"\nFailed nodes: {', '.join(results['failed'])}"

    log.info(summary)
    show_message_dialog("Batch Publish Results", summary)

    return results


def get_all_ayon_write_nodes():
    """
    Get all AYON write group nodes in the current script

    Returns:
        list: List of AYON write group nodes
    """
    ayon_write_nodes = []

    for node in nuke.allNodes():
        if node.Class() == "Group":
            # Check if it has AYON instance data
            if hasattr(node, "knob") and "creator_identifier" in [
                k.name() for k in node.allKnobs()
            ]:
                # Check if it's a write-type creator
                creator_id = node.knob("creator_identifier")
                if creator_id and "write" in creator_id.value().lower():
                    ayon_write_nodes.append(node)

    return ayon_write_nodes
