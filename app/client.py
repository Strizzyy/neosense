# app/client.py
import asyncio
from typing import Optional, Dict, List, Any
from neo4j import GraphDatabase
from application_sdk.clients import ClientInterface
from application_sdk.observability.logger_adaptor import get_logger

logger = get_logger(__name__)

class Neo4jClient(ClientInterface):
    def __init__(self, uri: str, username: str, password: str):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None

    async def load(self):
        """Initialize the Neo4j driver and verify connectivity."""
        try:
            logger.info(f"Connecting to Neo4j at {self.uri}")
            
            def _create_driver():
                driver = GraphDatabase.driver(
                    self.uri, 
                    auth=(self.username, self.password),
                    # Add connection timeout and other configs
                    connection_timeout=30,
                    max_connection_lifetime=3600
                )
                return driver
            
            # Run the synchronous driver creation in a thread pool
            self.driver = await asyncio.get_event_loop().run_in_executor(None, _create_driver)
            
            # Verify connectivity after creating driver
            await self.verify_connectivity()
            logger.info("Neo4j driver loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Neo4j driver: {str(e)}")
            if self.driver:
                self.driver.close()
                self.driver = None
            raise

    async def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            try:
                def _close_driver():
                    self.driver.close()
                
                await asyncio.get_event_loop().run_in_executor(None, _close_driver)
                logger.info("Neo4j driver closed successfully")
            except Exception as e:
                logger.error(f"Error closing Neo4j driver: {str(e)}")
            finally:
                self.driver = None

    async def verify_connectivity(self):
        """Verify that we can connect to the Neo4j database."""
        if not self.driver:
            raise RuntimeError("Driver not initialized. Call load() first.")
        
        try:
            def _verify():
                self.driver.verify_connectivity()
                return True
            
            # Run the synchronous verify_connectivity in a thread pool
            await asyncio.get_event_loop().run_in_executor(None, _verify)
            logger.info("Neo4j connectivity verified successfully")
            
        except Exception as e:
            logger.error(f"Neo4j connectivity verification failed: {str(e)}")
            raise

    async def run_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dictionaries."""
        if not self.driver:
            await self.load()
        
        try:
            def _run_query():
                with self.driver.session() as session:
                    result = session.run(query, params or {})
                    return [record.data() for record in result]
            
            # Run the synchronous Neo4j operations in a thread pool
            results = await asyncio.get_event_loop().run_in_executor(None, _run_query)
            logger.debug(f"Query executed successfully, returned {len(results)} records")
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute query: {str(e)}")
            raise