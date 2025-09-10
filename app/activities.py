# app/activities.py

import os
from typing import Dict
from temporalio import activity
from application_sdk.activities import ActivitiesInterface
from application_sdk.observability.logger_adaptor import get_logger
from .client import Neo4jClient
from .handler import Neo4jHandler

logger = get_logger(__name__)

class Neo4jActivities(ActivitiesInterface):
    
    def __init__(self):
        self.handler: Neo4jHandler | None = None

    async def _setup_state_if_needed(self, workflow_args: dict) -> None:
        if self.handler is None:
            uri = os.environ.get("NEO4J_URI")
            username = os.environ.get("NEO4J_USERNAME") 
            password = os.environ.get("NEO4J_PASSWORD")
            client = Neo4jClient(uri=uri, username=username, password=password)
            self.handler = Neo4jHandler(client=client)
            await self.handler.load()

    @activity.defn
    async def preflight_check(self, workflow_args: dict) -> bool:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.preflight_check()

    @activity.defn
    async def fetch_node_labels(self, workflow_args: dict) -> list[str]:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.get_node_labels()

    @activity.defn
    async def fetch_relationship_types(self, workflow_args: dict) -> list[str]:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.get_relationship_types()

    @activity.defn
    async def fetch_property_keys(self, workflow_args: dict) -> list[str]:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.get_property_keys()
    
    @activity.defn
    async def fetch_schema_info(self, workflow_args: dict) -> Dict:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.get_schema_info()

    @activity.defn
    async def fetch_quality_and_context(self, workflow_args: dict) -> Dict:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.get_quality_and_context()

    # --- NEW ACTIVITY ---
    @activity.defn
    async def fetch_graph_statistics_and_indexes(self, workflow_args: dict) -> Dict:
        await self._setup_state_if_needed(workflow_args)
        return await self.handler.get_graph_statistics_and_indexes()