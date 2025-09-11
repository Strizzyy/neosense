# app/activities.py

import os
from typing import Dict, Any
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
            try:
                logger.info("Setting up Neo4j handler with dynamic credentials")
                
                # Get credentials from workflow args or fall back to environment variables
                credentials = workflow_args.get("neo4j_credentials", {})
                
                uri = credentials.get("neo4j_uri") or os.environ.get("NEO4J_URI")
                username = credentials.get("neo4j_username") or os.environ.get("NEO4J_USERNAME")
                password = credentials.get("neo4j_password") or os.environ.get("NEO4J_PASSWORD")
                
                if not all([uri, username, password]):
                    raise ValueError("Missing required Neo4j credentials. Please provide them via the frontend form or environment variables.")
                
                logger.info(f"Connecting to Neo4j at {uri} with username {username}")
                
                client = Neo4jClient(uri=uri, username=username, password=password)
                self.handler = Neo4jHandler(client=client)
                await self.handler.load()
                
                logger.info("Neo4j handler setup completed successfully")
            except Exception as e:
                logger.error(f"Failed to setup Neo4j handler: {str(e)}")
                self.handler = None
                raise

    @activity.defn
    async def get_workflow_args(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and prepare workflow arguments from config."""
        logger.info("Preparing workflow arguments with credentials")
        
        # Extract Neo4j credentials from config
        neo4j_credentials = workflow_config.get("neo4j_credentials", {})
        
        return {
            "workflow_id": workflow_config.get("workflow_id", "unknown"),
            "config": workflow_config,
            "neo4j_credentials": neo4j_credentials
        }

    @activity.defn
    async def preflight_check(self, workflow_args: dict) -> bool:
        """Perform preflight connectivity check."""
        await self._setup_state_if_needed(workflow_args)
        if not self.handler: 
            raise RuntimeError("Handler not initialized")
        logger.info("Running preflight check")
        return await self.handler.preflight_check()

    @activity.defn
    async def fetch_node_labels(self, workflow_args: dict) -> list[str]:
        """Fetch all node labels from the Neo4j database."""
        await self._setup_state_if_needed(workflow_args)
        if not self.handler: 
            raise RuntimeError("Handler not initialized")
        logger.info("Fetching node labels")
        return await self.handler.get_node_labels()

    @activity.defn
    async def fetch_relationship_types(self, workflow_args: dict) -> list[str]:
        """Fetch all relationship types from the Neo4j database."""
        await self._setup_state_if_needed(workflow_args)
        if not self.handler: 
            raise RuntimeError("Handler not initialized")
        logger.info("Fetching relationship types")
        return await self.handler.get_relationship_types()

    @activity.defn
    async def fetch_schema_info(self, workflow_args: dict) -> Dict[str, Any]:
        """Fetch schema information including constraints, property types, and lineage."""
        await self._setup_state_if_needed(workflow_args)
        if not self.handler: 
            raise RuntimeError("Handler not initialized")
        logger.info("Fetching schema information")
        return await self.handler.get_schema_info()

    @activity.defn
    async def fetch_quality_and_context(self, workflow_args: dict) -> Dict[str, Any]:
        """Fetch data quality metrics and business context."""
        await self._setup_state_if_needed(workflow_args)
        if not self.handler: 
            raise RuntimeError("Handler not initialized")
        logger.info("Fetching quality metrics and business context")
        return await self.handler.get_quality_and_context()

    @activity.defn
    async def fetch_graph_statistics_and_indexes(self, workflow_args: dict) -> Dict[str, Any]:
        """Fetch graph statistics and index information."""
        await self._setup_state_if_needed(workflow_args)
        if not self.handler: 
            raise RuntimeError("Handler not initialized")
        logger.info("Fetching graph statistics and indexes")
        return await self.handler.get_graph_statistics_and_indexes()

    @activity.defn
    async def store_metadata_result(self, data: Dict[str, Any]) -> bool:
        """Store the metadata result for frontend access."""
        try:
            workflow_id = data.get("workflow_id")
            result = data.get("result")
            
            logger.info(f"Storing metadata result for workflow: {workflow_id}")
            logger.info(f"Result contains {len(result)} main sections")
            
            # Store in a simple file that the API can read
            import json
            import os
            
            results_dir = "workflow_results"
            os.makedirs(results_dir, exist_ok=True)
            
            result_file = os.path.join(results_dir, f"{workflow_id}.json")
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Stored result to file: {result_file}")
            
            # Also store the latest result as "latest.json" for easy access
            latest_file = os.path.join(results_dir, "latest.json")
            with open(latest_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Stored latest result to: {latest_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store metadata result: {e}")
            return False