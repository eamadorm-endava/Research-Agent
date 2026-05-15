import sys
import click
from google.cloud import aiplatform_v1
from google.api_core.client_options import ClientOptions
from loguru import logger


@click.command()
@click.option("--project", required=True, help="GCP Project ID")
@click.option(
    "--location", default="us-central1", help="GCP Region (default: us-central1)"
)
@click.option("--engine-id", required=True, help="Reasoning Engine ID")
@click.option(
    "--force/--no-force",
    default=True,
    help="Force deletion of child resources (default: True)",
)
def main(project, location, engine_id, force):
    """
    Deletes a Vertex AI Reasoning Engine using Click for CLI parameters.
    """
    # Construct paths and endpoints
    resource_name = (
        f"projects/{project}/locations/{location}/reasoningEngines/{engine_id}"
    )
    api_endpoint = f"{location}-aiplatform.googleapis.com"

    # Configure client
    client_options = ClientOptions(api_endpoint=api_endpoint)
    client = aiplatform_v1.ReasoningEngineServiceClient(client_options=client_options)

    logger.info(f"Initiating deletion for: {resource_name}")

    try:
        # Prepare the request
        request = aiplatform_v1.DeleteReasoningEngineRequest(
            name=resource_name,
            force=force,
        )

        # Execute the deletion
        operation = client.delete_reasoning_engine(request=request)

        logger.info("Waiting for deletion operation to complete...")
        operation.result()
        logger.success(f"Reasoning Engine {engine_id} deleted successfully.")
    except Exception as e:
        logger.error(f"Failed to delete Reasoning Engine: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
