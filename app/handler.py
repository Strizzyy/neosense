import os
from typing import List, Dict, Any
from application_sdk.handlers import HandlerInterface
from application_sdk.observability.decorators.observability_decorator import observability
from application_sdk.observability.logger_adaptor import get_logger
from application_sdk.observability.metrics_adaptor import get_metrics
from application_sdk.observability.traces_adaptor import get_traces
from .client import Neo4jClient

# --- ADDED: Imports for the observability decorator ---
logger = get_logger(__name__)
metrics = get_metrics()
traces = get_traces()


class Neo4jHandler(HandlerInterface):
    def __init__(self, client: Neo4jClient):
        self.client = client

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def load(self, **kwargs):
        """Initialize the handler by loading the client."""
        try:
            logger.info("Loading Neo4j handler")
            await self.client.load()
            logger.info("Neo4j handler loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Neo4j handler: {str(e)}")
            raise

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def test_auth(self, **kwargs) -> bool:
        """Test authentication by running a simple query."""
        try:
            logger.info("Testing Neo4j authentication")
            result = await self.client.run_query("RETURN 1 as test")
            logger.info(f"Authentication test successful: {result}")
            return True
        except Exception as e:
            logger.error(f"Authentication test failed: {str(e)}")
            raise

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def preflight_check(self, **kwargs) -> bool:
        """Run preflight checks to verify system readiness."""
        try:
            logger.info("Running Neo4j preflight check")
            
            # Test basic connectivity
            await self.client.verify_connectivity()
            
            # Test authentication with a simple query
            await self.test_auth()
            
            logger.info("Preflight check successful")
            return True
            
        except Exception as e:
            logger.error(f"Preflight check failed: {str(e)}")
            raise

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_node_labels(self) -> List[str]:
        """Get all node labels from the Neo4j database."""
        try:
            # Use direct query instead of reading from file for now
            query = "CALL db.labels() YIELD label RETURN label"
            results = await self.client.run_query(query)
            labels = [record['label'] for record in results]
            logger.info(f"Retrieved {len(labels)} node labels")
            return labels
        except Exception as e:
            logger.error(f"Failed to get node labels: {str(e)}")
            raise

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_relationship_types(self) -> List[str]:
        """Get all relationship types from the Neo4j database."""
        try:
            # Use direct query instead of reading from file for now
            query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            results = await self.client.run_query(query)
            rels = [record['relationshipType'] for record in results]
            logger.info(f"Retrieved {len(rels)} relationship types")
            return rels
        except Exception as e:
            logger.error(f"Failed to get relationship types: {str(e)}")
            raise

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_property_keys(self) -> List[str]:
        """Get all property keys from the Neo4j database."""
        try:
            # Use direct query instead of reading from file for now  
            query = "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey"
            results = await self.client.run_query(query)
            props = [record['propertyKey'] for record in results]
            logger.info(f"Retrieved {len(props)} property keys")
            return props
        except Exception as e:
            logger.error(f"Failed to get property keys: {str(e)}")
            raise

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def fetch_metadata(self, **kwargs) -> Dict[str, Any]:
        """Fetch all metadata from Neo4j database."""
        try:
            logger.info("Fetching all Neo4j metadata")
            return {
                "node_labels": await self.get_node_labels(),
                "relationship_types": await self.get_relationship_types(),
                "property_keys": await self.get_property_keys()
            }
        except Exception as e:
            logger.error(f"Failed to fetch metadata: {str(e)}")
            raise

    def _read_query(self, filename: str) -> str:
        """Read a query from the queries directory."""
        try:
            path = os.path.join(os.path.dirname(__file__), "queries", filename)
            if not os.path.exists(path):
                logger.warning(f"Query file not found: {path}")
                raise FileNotFoundError(f"Query file not found: {path}")
            
            with open(path, "r") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read query file {filename}: {str(e)}")
            raise