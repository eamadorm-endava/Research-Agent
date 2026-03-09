# Check https://docs.cloud.google.com/python/docs/reference/vertexai/latest
# and https://googlecloudplatform.github.io/agent-starter-pack/guide/development-guide.html
import vertexai
from vertexai._genai import _agent_engines_utils
from vertexai._genai.types import AgentEngine, AgentEngineConfig
from typing import Optional, Any
import click
import logging
import importlib
import datetime
import inspect
import asyncio


def generate_class_methods_from_agent(agent_instance: Any) -> list[dict[str, Any]]:
    """Generate method specifications with schemas from agent's register_operations().

    See: https://docs.cloud.google.com/agent-builder/agent-engine/use/custom#supported-operations
    """
    registered_operations = _agent_engines_utils._get_registered_operations(
        agent=agent_instance
    )
    class_methods_spec = _agent_engines_utils._generate_class_methods_spec_or_raise(
        agent=agent_instance,
        operations=registered_operations,
    )
    class_methods_list = [
        _agent_engines_utils._to_dict(method_spec) for method_spec in class_methods_spec
    ]
    return class_methods_list


def parse_key_value_pairs(kv_string: Optional[str]) -> dict[str, str]:
    """Parse key-value pairs from a comma-separated KEY=VALUE string."""
    result = {}
    if kv_string:
        for pair in kv_string.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                result[key.strip()] = value.strip()
            else:
                logging.warning(f"Skipping malformed key-value pair: {pair}")
    return result


# Allow to run this script passing the next options
@click.command()
@click.option(
    "--project",
    default=None,
    help="GCP project ID (defaults to application default credentials)",
)
@click.option(
    "--location",
    default="us-central1",
    help="GCP region (defaults to us-central1)",
)
@click.option(
    "--display-name",
    default="testing-agent-deployment",
    help="Display name for the agent engine",
)
@click.option(
    "--description",
    default="BigQuery Agent",
    help="Description of the agent",
)
@click.option(
    "--source-packages",
    multiple=True,
    default=["./agent/core_agent"],
    help="Source packages to deploy. Can be specified multiple times (e.g., --source-packages=./app --source-packages=./lib). The origin is the root where the command is executed",
)
@click.option(
    "--entrypoint-module",
    default="core_agent.agent",
    help="Python module path for the agent entrypoint (required)",
)
@click.option(
    "--entrypoint-object",
    default="app",
    help="Name of the agent instance at module level (required)",
)
@click.option(
    "--requirements-file",
    default="agent/core_agent/requirements.txt",
    help="Path to requirements.txt file",
)
@click.option(
    "--set-env-vars",
    default=None,
    help="Comma-separated list of environment variables in KEY=VALUE format",
)
@click.option(
    "--service-account",
    default=None,
    help="Service account email to use for the agent engine",
)
@click.option(
    "--min-instances",
    type=int,
    default=1,
    help="Minimum number of instances (default: 1)",
)
@click.option(
    "--max-instances",
    type=int,
    default=10,
    help="Maximum number of instances (default: 10)",
)
@click.option(
    "--cpu",
    default="4",
    help="CPU limit (default: 4)",
)
@click.option(
    "--memory",
    default="8Gi",
    help="Memory limit (default: 8Gi)",
)
@click.option(
    "--container-concurrency",
    type=int,
    default=9,
    help="Container concurrency (default: 9)",
)
@click.option(
    "--num-workers",
    type=int,
    default=1,
    help="Number of worker processes (default: 1)",
)
def deploy_agent_engine_app(
    project: str | None,
    location: str,
    display_name: str,
    description: str,
    source_packages: tuple[str, ...],
    entrypoint_module: str,
    entrypoint_object: str,
    requirements_file: str,
    set_env_vars: str | None,
    service_account: str | None,
    min_instances: int,
    max_instances: int,
    cpu: str,
    memory: str,
    container_concurrency: int,
    num_workers: int,
) -> AgentEngine:
    """
    Deploy the agent engine app to VertexAI
    """
    logging.basicConfig(level=logging.INFO)

    # Parse CLI env vars
    env_vars = parse_key_value_pairs(set_env_vars)

    # Set deployment-specific environment variables
    env_vars["GOOGLE_CLOUD_REGION"] = location
    env_vars["NUM_WORKERS"] = str(num_workers)

    # Enable telemetry by default for Agent Engine
    env_vars.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")
    env_vars.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

    # Log deployment parameters
    click.echo("\n Deployment Parameters:")
    params = [
        ("Project", project),
        ("Location", location),
        ("Display Name", display_name),
        ("Min Instances", min_instances),
        ("Max Instances", max_instances),
        ("CPU", cpu),
        ("Memory", memory),
        ("Container Concurrency", container_concurrency),
    ]
    if service_account:
        params.append(("Service Account", service_account))
    for name, value in params:
        click.echo(f"  {name}: {value}")

    source_packages_list = list(source_packages)

    client = vertexai.Client(
        project=project,
        location=location,
    )
    vertexai.init(project=project, location=location)

    # Dynamically import the agent instance to generate class_methods
    logging.info(f"Importing {entrypoint_module}.{entrypoint_object}")
    module = importlib.import_module(entrypoint_module)
    agent_instance = getattr(module, entrypoint_object)

    # If the agent_instance is a coroutine, await it to get the actual instance
    if inspect.iscoroutine(agent_instance):
        logging.info(f"Detected coroutine, awaiting {entrypoint_object}...")
        agent_instance = asyncio.run(agent_instance)

    # Generate class methods spec from register_operations
    class_methods_list = generate_class_methods_from_agent(agent_instance)

    config = AgentEngineConfig(
        display_name=display_name,
        description=description,
        source_packages=source_packages_list,
        entrypoint_module=entrypoint_module,
        entrypoint_object=entrypoint_object,
        class_methods=class_methods_list,
        env_vars=env_vars,
        service_account=service_account,
        requirements_file=requirements_file,
        min_instances=min_instances,
        max_instances=max_instances,
        resource_limits={"cpu": cpu, "memory": memory},
        container_concurrency=container_concurrency,
        agent_framework="google-adk",
    )

    # Check if an agent with this name already exists
    existing_agents = list(client.agent_engines.list())
    matching_agents = [
        agent
        for agent in existing_agents
        if agent.api_resource.display_name == display_name
    ]

    # Deploy the agent (create or update)
    action = "Updating" if matching_agents else "Creating"
    click.echo(f"\n🚀 {action} agent: {display_name} (this can take 3-5 minutes)...")

    if matching_agents:
        remote_agent = client.agent_engines.update(
            name=matching_agents[0].api_resource.name, config=config
        )
    else:
        remote_agent = client.agent_engines.create(config=config)

    metadata = {
        "remote_agent_engine_id": remote_agent.api_resource.name,
        "deployment_target": "agent_engine",
        "is_a2a": False,
        "deployment_timestamp": datetime.datetime.now().isoformat(),
    }
    logging.info(metadata)

    return remote_agent


if __name__ == "__main__":
    deploy_agent_engine_app()
