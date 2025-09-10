"""
This file contains the activities definition for the Neo4j metadata extraction application.
"""

import os  # <-- ADDED THIS IMPORT
from temporalio import activity
from application_sdk.activities import ActivitiesInterface
from application_sdk.observability.logger_adaptor import get_logger
from .client import Neo4jClient
from .handler import Neo4jHandler

logger = get_logger(__name__)

class Neo4jActivities(ActivitiesInterface):
    
    def __init__(self):
        # The handler is initialized once per worker process, making it efficient.
        self.handler: Neo4jHandler | None = None

    async def _setup_state_if_needed(self, workflow_args: dict) -> None:
        """
        Initializes the Neo4j handler using connection details from environment variables.
        """
        if self.handler is None:
            try:
                logger.info("Setting up Neo4j handler from environment variables")
                
                # --- THIS IS THE UPDATED LOGIC ---
                # Read connection details directly from environment variables, ignoring workflow_args.
                uri = os.environ.get("NEO4J_URI")
                username = os.environ.get("NEO4J_USERNAME") 
                password = os.environ.get("NEO4J_PASSWORD")
                # ---------------------------------
                
                if not all([uri, username, password]):
                    raise ValueError("Missing required Neo4j environment variables: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
                
                logger.info(f"Creating Neo4j client for URI: {uri}")
                
                client = Neo4jClient(
                    uri=uri,
                    username=username,
                    password=password
                )
                
                self.handler = Neo4jHandler(client=client)
                await self.handler.load() # A method in your handler to establish connection
                
                logger.info("Neo4j handler setup completed successfully")
                
            except Exception as e:
                logger.error(f"Failed to setup Neo4j handler: {str(e)}")
                self.handler = None  # Reset handler on failure
                raise

    # get_workflow_args is correctly inherited from ActivitiesInterface.

    @activity.defn
    async def preflight_check(self, workflow_args: dict) -> bool:
        """Checks if a connection to Neo4j can be established successfully."""
        try:
            logger.info("Starting preflight check")
            await self._setup_state_if_needed(workflow_args)
            
            if not self.handler:
                raise RuntimeError("Handler not initialized")
            
            result = await self.handler.preflight_check()
            logger.info(f"Preflight check completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Preflight check failed: {str(e)}")
            raise

    @activity.defn
    async def fetch_node_labels(self, workflow_args: dict) -> list[str]:
        """Fetches all node labels from Neo4j."""
        try:
            logger.info("Fetching node labels")
            await self._setup_state_if_needed(workflow_args)
            
            if not self.handler:
                raise RuntimeError("Handler not initialized")
            
            labels = await self.handler.get_node_labels()
            logger.info(f"Retrieved {len(labels)} node labels")
            return labels
            
        except Exception as e:
            logger.error(f"Failed to fetch node labels: {str(e)}")
            raise

    @activity.defn
    async def fetch_relationship_types(self, workflow_args: dict) -> list[str]:
        """Fetches all relationship types from Neo4j."""
        try:
            logger.info("Fetching relationship types")
            await self._setup_state_if_needed(workflow_args)
            
            if not self.handler:
                raise RuntimeError("Handler not initialized")
            
            rels = await self.handler.get_relationship_types()
            logger.info(f"Retrieved {len(rels)} relationship types")
            return rels
            
        except Exception as e:
            logger.error(f"Failed to fetch relationship types: {str(e)}")
            raise

    @activity.defn
    async def fetch_property_keys(self, workflow_args: dict) -> list[str]:
        """Fetches all property keys from Neo4j."""
        try:
            logger.info("Fetching property keys")
            await self._setup_state_if_needed(workflow_args)
            
            if not self.handler:
                raise RuntimeError("Handler not initialized")
            
            props = await self.handler.get_property_keys()
            logger.info(f"Retrieved {len(props)} property keys")
            return props
            
        except Exception as e:
            logger.error(f"Failed to fetch property keys: {str(e)}")
            raise