import sys
import click
from google.cloud import aiplatform_v1
from google.api_core.client_options import ClientOptions
from loguru import logger


@click.command()
@click.option("--project", required=True, help="GCP Project ID")
@click.option("--location", required=True, help="GCP Region for the Reasoning Engine")
@click.option("--display-name", required=True, help="Reasoning Engine Display Name")
@click.option(
    "--force/--no-force",
    default=True,
    help="Force deletion of child resources (default: True)",
)
def main(project, location, display_name, force):
    """
    Deletes a Vertex AI Reasoning Engine by display name.
    """
    # Construct paths and endpoints
    parent = f"projects/{project}/locations/{location}"
    api_endpoint = f"{location}-aiplatform.googleapis.com"

    # Configure client
    client_options = ClientOptions(api_endpoint=api_endpoint)
    client = aiplatform_v1.ReasoningEngineServiceClient(client_options=client_options)

    logger.info(f"Looking up Reasoning Engine by display name: {display_name}")

    try:
        request = aiplatform_v1.ListReasoningEnginesRequest(
            parent=parent, filter=f'display_name="{display_name}"'
        )
        response = client.list_reasoning_engines(request=request)

        engines = list(response)
        if not engines:
            logger.warning(
                f"No Reasoning Engine found with display name '{display_name}'. Skipping deletion."
            )
            return

        for engine in engines:
            resource_name = engine.name
            logger.info(f"Initiating deletion for: {resource_name}")

            # Prepare the request
            del_request = aiplatform_v1.DeleteReasoningEngineRequest(
                name=resource_name,
                force=force,
            )

            # Execute the deletion
            operation = client.delete_reasoning_engine(request=del_request)

            logger.info(
                f"Waiting for deletion operation to complete for {resource_name}..."
            )
            operation.result()
            logger.success(f"Reasoning Engine {resource_name} deleted successfully.")
    except Exception as e:
        logger.error(f"Failed to delete Reasoning Engine: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
