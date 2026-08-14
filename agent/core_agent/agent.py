from loguru import logger
from google.adk.tools import VertexAiSearchTool
from google.adk.agents import Agent
from google.adk.apps.app import App

logger.info("ADK Single-Agent application initialized and ready for execution.")

DATASTORE_PATH = "projects/<gcp-project-location>/locations/<datastore-location>/collections/default_collection/dataStores/<gemini-enterprise-datastore-id>"
vertex_search_tool = VertexAiSearchTool(data_store_id=DATASTORE_PATH)
APP_NAME_VSEARCH = "core_agent"

# Agent Definition
root_agent = Agent(
    name=APP_NAME_VSEARCH,
    model="gemini-2.5-flash",
    tools=[vertex_search_tool],
    instruction=f"""You are a helpful assistant that answers questions based on information found in the document store: {DATASTORE_PATH}.
    Use the search tool to find relevant information before answering.
    If the answer isn't in the documents, say that you couldn't find the information.
    """,
    description="Answers questions using a specific Agent Search datastore.",
)

app = App(
    name=APP_NAME_VSEARCH,
    root_agent=root_agent,
)
