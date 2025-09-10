# app/handler.py

import os
from typing import List, Dict, Any
from datetime import date, datetime
from application_sdk.handlers import HandlerInterface
from application_sdk.observability.decorators.observability_decorator import observability
from application_sdk.observability.logger_adaptor import get_logger
from application_sdk.observability.metrics_adaptor import get_metrics
from application_sdk.observability.traces_adaptor import get_traces
from .client import Neo4jClient

logger = get_logger(__name__)
metrics = get_metrics()
traces = get_traces()

class Neo4jHandler(HandlerInterface):
    def __init__(self, client: Neo4jClient):
        self.client = client

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def test_auth(self, **kwargs) -> bool: 
        await self.client.verify_connectivity()
        return True
    
    @observability(logger=logger, metrics=metrics, traces=traces)
    async def fetch_metadata(self, **kwargs) -> Dict[str, Any]: 
        return {}
    
    @observability(logger=logger, metrics=metrics, traces=traces)
    async def load(self, **kwargs): 
        await self.client.load()
    
    @observability(logger=logger, metrics=metrics, traces=traces)
    async def preflight_check(self, **kwargs) -> bool: 
        await self.client.verify_connectivity()
        return True

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_node_labels(self) -> List[str]:
        query = "CALL db.labels() YIELD label RETURN label ORDER BY label"
        results = await self.client.run_query(query)
        return [record['label'] for record in results]

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_relationship_types(self) -> List[str]:
        query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType"
        results = await self.client.run_query(query)
        return [record['relationshipType'] for record in results]

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_schema_info(self) -> Dict[str, Any]:
        logger.info("Fetching comprehensive schema information.")
        
        # Get constraints
        constraints_query = "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties"
        constraints = await self.client.run_query(constraints_query)
        
        # Get node property types
        node_property_types = {}
        labels = await self.get_node_labels()
        
        for label in labels:
            # Get sample of nodes to determine property types
            sample_query = f"MATCH (n:`{label}`) RETURN n LIMIT 10"
            sample_results = await self.client.run_query(sample_query)
            
            if sample_results:
                properties = {}
                # Analyze all samples to get comprehensive property info
                for result in sample_results:
                    node_data = result['n']
                    for key, value in node_data.items():
                        if key not in properties:
                            if isinstance(value, bool):
                                properties[key] = "BOOLEAN"
                            elif isinstance(value, int):
                                properties[key] = "INTEGER" 
                            elif isinstance(value, float):
                                properties[key] = "FLOAT"
                            elif isinstance(value, date):
                                properties[key] = "DATE"
                            elif isinstance(value, datetime):
                                properties[key] = "DATETIME"
                            else:
                                properties[key] = "STRING"
                
                node_property_types[label] = properties
        
        # Get lineage information - simplified and more reliable approach
        lineage = await self._get_lineage_info()
        
        return {
            "constraints": constraints,
            "node_property_types": node_property_types,
            "lineage": lineage
        }

    async def _get_lineage_info(self) -> List[str]:
        """Extract lineage/dependency information from the graph"""
        try:
            # Get relationship patterns
            pattern_query = """
            MATCH (a)-[r]->(b)
            WITH labels(a)[0] AS source_label, type(r) AS rel_type, labels(b)[0] AS target_label
            RETURN DISTINCT source_label, rel_type, target_label
            ORDER BY source_label, rel_type, target_label
            """
            
            patterns_result = await self.client.run_query(pattern_query)
            lineage_patterns = []
            
            for record in patterns_result:
                source = record['source_label']
                rel = record['rel_type'] 
                target = record['target_label']
                pattern = f"(:{source})-[:{rel}]->(:{target})"
                lineage_patterns.append(pattern)
            
            return lineage_patterns
            
        except Exception as e:
            logger.warning(f"Failed to extract lineage info: {e}")
            return []

    @observability(logger=logger, metrics=metrics, traces=traces)
    async def get_quality_and_context(self) -> Dict[str, Any]:
        """Get data quality metrics and business context"""
        
        quality_metrics = {}
        business_context = {}
        
        try:
            # Customer email quality check
            customer_email_query = """
            MATCH (c:Customer) 
            RETURN count(c) AS total, 
                   count(c.email) AS non_null,
                   count(DISTINCT c.email) AS unique_emails
            """
            customer_email_res = (await self.client.run_query(customer_email_query))[0]
            
            quality_metrics["Customer.email"] = {
                "metric_type": "Null Count",
                "total_records": customer_email_res['total'],
                "null_count": customer_email_res['total'] - customer_email_res['non_null'],
                "unique_values": customer_email_res.get('unique_emails', 0)
            }
            
            # Product category quality check  
            product_category_query = """
            MATCH (p:Product) 
            RETURN count(p) as total, 
                   count(p.category) as non_null_categories,
                   count(DISTINCT p.category) as unique_categories
            """
            product_category_res = (await self.client.run_query(product_category_query))[0]
            
            quality_metrics["Product.category"] = {
                "metric_type": "Uniqueness",
                "total_records": product_category_res['total'],
                "null_count": product_category_res['total'] - product_category_res['non_null_categories'],
                "unique_values": product_category_res['unique_categories']
            }
            
            # Additional quality metrics for other important fields
            order_status_query = """
            MATCH (o:Order)
            RETURN count(o) as total,
                   count(o.status) as non_null_status,
                   count(DISTINCT o.status) as unique_statuses
            """
            order_status_res = (await self.client.run_query(order_status_query))[0]
            
            quality_metrics["Order.status"] = {
                "metric_type": "Completeness", 
                "total_records": order_status_res['total'],
                "null_count": order_status_res['total'] - order_status_res['non_null_status'],
                "unique_values": order_status_res['unique_statuses']
            }
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
        
        try:
            # Business context - get descriptions and meaningful business info
            product_desc_query = """
            MATCH (p:Product) 
            WHERE p.description IS NOT NULL 
            RETURN p.name AS product_name, 
                   p.description AS product_description,
                   p.category AS category,
                   p.price AS price
            ORDER BY p.name
            """
            product_descriptions = await self.client.run_query(product_desc_query)
            
            # Customer segments
            customer_segments_query = """
            MATCH (c:Customer)
            RETURN c.isPremium as is_premium, count(c) as customer_count
            """
            customer_segments = await self.client.run_query(customer_segments_query)
            
            # Order statistics
            order_stats_query = """
            MATCH (o:Order)
            RETURN o.status as order_status, count(o) as order_count
            ORDER BY order_count DESC
            """
            order_stats = await self.client.run_query(order_stats_query)
            
            business_context = {
                "product_catalog": {
                    "descriptions": product_descriptions,
                    "total_products": len(product_descriptions)
                },
                "customer_segments": customer_segments,
                "order_statistics": order_stats
            }
            
        except Exception as e:
            logger.error(f"Error gathering business context: {e}")
            business_context = {"error": f"Failed to gather context: {str(e)}"}
        
        return {
            "quality_metrics": quality_metrics,
            "business_context": business_context
        }

    @observability(logger=logger, metrics=metrics, traces=traces) 
    async def get_graph_statistics_and_indexes(self) -> Dict[str, Any]:
        """Get graph statistics and index information"""
        
        try:
            # Get indexes
            indexes_query = "SHOW INDEXES YIELD name, type, labelsOrTypes, properties"
            indexes_result = await self.client.run_query(indexes_query)
            
            # Get basic graph statistics
            stats_queries = {
                "total_nodes": "MATCH (n) RETURN count(n) as count",
                "total_relationships": "MATCH ()-[r]->() RETURN count(r) as count",
                "node_counts_by_label": "MATCH (n) RETURN labels(n)[0] as label, count(n) as count ORDER BY count DESC",
                "relationship_counts_by_type": "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC"
            }
            
            statistics = {}
            for stat_name, query in stats_queries.items():
                try:
                    result = await self.client.run_query(query)
                    statistics[stat_name] = result
                except Exception as e:
                    logger.warning(f"Failed to get {stat_name}: {e}")
                    statistics[stat_name] = f"Error: {str(e)}"
            
            return {
                "statistics": statistics,
                "indexes": indexes_result
            }
            
        except Exception as e:
            logger.error(f"Error getting graph statistics: {e}")
            return {
                "statistics": {"error": f"Failed to get statistics: {str(e)}"},
                "indexes": []
            }