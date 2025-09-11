# app/workflow.py

import asyncio
from datetime import timedelta
from typing import Any, Dict, Sequence, Callable
from temporalio import workflow
from temporalio.common import RetryPolicy
from application_sdk.workflows import WorkflowInterface
from application_sdk.activities import ActivitiesInterface
from application_sdk.observability.decorators.observability_decorator import observability
from application_sdk.observability.logger_adaptor import get_logger
from application_sdk.observability.metrics_adaptor import get_metrics
from application_sdk.observability.traces_adaptor import get_traces
from .activities import Neo4jActivities

logger = get_logger(__name__)
metrics = get_metrics()
traces = get_traces()


@workflow.defn
class Neo4jWorkflow(WorkflowInterface):
    def __init__(self):
        super().__init__()
        self._metadata_result: dict | None = None
        self.activities_cls = Neo4jActivities()


    @observability(logger=logger, metrics=metrics, traces=traces)
    @workflow.run
    async def run(self, workflow_config: Dict[str, Any]) -> dict:
        timeout = timedelta(minutes=5)
        workflow_args = await workflow.execute_activity_method(
            self.activities_cls.get_workflow_args, 
            workflow_config, 
            start_to_close_timeout=timedelta(minutes=1),
        )
        
        try:
            # Enhanced preflight check with retry policy
            await workflow.execute_activity_method(
                self.activities_cls.preflight_check, 
                workflow_args, 
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    maximum_attempts=3,
                    backoff_coefficient=2.0
                )
            )

            # Execute all data gathering activities in parallel with enhanced error handling
            logger.info("Starting parallel metadata extraction activities")
            results = await asyncio.gather(
                workflow.execute_activity_method(
                    self.activities_cls.fetch_node_labels, 
                    workflow_args, 
                    start_to_close_timeout=timeout,
                    retry_policy=RetryPolicy(maximum_attempts=2)
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_relationship_types, 
                    workflow_args, 
                    start_to_close_timeout=timeout,
                    retry_policy=RetryPolicy(maximum_attempts=2)
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_schema_info, 
                    workflow_args, 
                    start_to_close_timeout=timeout,
                    retry_policy=RetryPolicy(maximum_attempts=2)
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_quality_and_context, 
                    workflow_args, 
                    start_to_close_timeout=timeout,
                    retry_policy=RetryPolicy(maximum_attempts=2)
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_graph_statistics_and_indexes, 
                    workflow_args, 
                    start_to_close_timeout=timeout,
                    retry_policy=RetryPolicy(maximum_attempts=2)
                ),
                return_exceptions=True  # Enhanced error handling
            )

            # Enhanced result processing with error handling
            labels, relationship_types, schema_info, quality_context, advanced_info = results
            
            # Check for any failed activities
            failed_activities = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    activity_names = ["fetch_node_labels", "fetch_relationship_types", "fetch_schema_info", "fetch_quality_and_context", "fetch_graph_statistics_and_indexes"]
                    failed_activities.append(activity_names[i])
                    logger.error(f"Activity {activity_names[i]} failed: {result}")
            
            if failed_activities:
                logger.warning(f"Some activities failed: {failed_activities}. Proceeding with partial results.")
                # Set default values for failed activities
                if isinstance(labels, Exception):
                    labels = []
                if isinstance(relationship_types, Exception):
                    relationship_types = []
                if isinstance(schema_info, Exception):
                    schema_info = {}
                if isinstance(quality_context, Exception):
                    quality_context = {}
                if isinstance(advanced_info, Exception):
                    advanced_info = {}
            
            # Structure the metadata according to requirements
            self._metadata_result = {
                "Schema Information": {
                    # Column names and data types (adapted for graph - node labels and properties)
                    "node_labels": labels,
                    "relationship_types": relationship_types,
                    "node_property_details": schema_info.get("node_property_types", {}),
                    "constraints": schema_info.get("constraints", []),
                    "indexes": advanced_info.get("indexes", [])
                },
                "Business Context": {
                    # Business descriptions and context
                    "product_catalog": quality_context.get("business_context", {}).get("product_catalog", {}),
                    "customer_segments": quality_context.get("business_context", {}).get("customer_segments", []),
                    "order_statistics": quality_context.get("business_context", {}).get("order_statistics", []),
                    "graph_statistics": advanced_info.get("statistics", {})
                },
                "Lineage Information": {
                    # Data relationships and dependencies
                    "graph_dependencies": schema_info.get("lineage", []),
                    "relationship_patterns": self._extract_relationship_patterns(schema_info.get("lineage", [])),
                    "data_flow": self._analyze_data_flow(labels, relationship_types)
                },
                "Quality Metrics": {
                    # Data quality indicators
                    **quality_context.get("quality_metrics", {}),
                    "data_completeness": self._calculate_completeness_summary(quality_context.get("quality_metrics", {})),
                    "data_uniqueness": self._calculate_uniqueness_summary(quality_context.get("quality_metrics", {}))
                }
            }

            # Log the complete results for demo purposes
            self._log_metadata_results(self._metadata_result)
            
            # Store the result for frontend access
            await self._store_result_for_frontend(self._metadata_result)
            
            return self._metadata_result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            # Return partial results with error information
            self._metadata_result = {
                "Schema Information": {"error": f"Failed to extract schema: {str(e)}"},
                "Business Context": {"error": f"Failed to extract context: {str(e)}"},
                "Lineage Information": {"error": f"Failed to extract lineage: {str(e)}"},
                "Quality Metrics": {"error": f"Failed to extract metrics: {str(e)}"}
            }
            
            # Still try to store the error results
            try:
                await self._store_result_for_frontend(self._metadata_result)
            except Exception as store_error:
                logger.warning(f"Failed to store error results: {store_error}")
            
            return self._metadata_result
            
        finally:
            await super().run(workflow_config)

    def _extract_relationship_patterns(self, lineage_list: list) -> Dict[str, Any]:
        """Extract and categorize relationship patterns"""
        if not lineage_list:
            return {"patterns": [], "summary": "No relationship patterns found"}
        
        patterns_by_type = {}
        for pattern in lineage_list:
            # Parse pattern like "(Customer)-[PLACED_ORDER]->(Order)"
            if "-[" in pattern and "]->" in pattern:
                rel_type = pattern.split("-[")[1].split("]->(")[0].replace(":", "")
                if rel_type not in patterns_by_type:
                    patterns_by_type[rel_type] = []
                patterns_by_type[rel_type].append(pattern)
        
        return {
            "patterns": lineage_list,
            "patterns_by_relationship_type": patterns_by_type,
            "total_patterns": len(lineage_list),
            "unique_relationship_types": len(patterns_by_type)
        }

    def _analyze_data_flow(self, node_labels: list, relationship_types: list) -> Dict[str, Any]:
        """Analyze potential data flow based on labels and relationships"""
        return {
            "entities": node_labels,
            "connections": relationship_types,
            "potential_flows": [
                f"{label1} -> {rel} -> {label2}" 
                for label1 in node_labels 
                for label2 in node_labels 
                for rel in relationship_types
                if label1 != label2
            ][:10]  # Limit to first 10 to avoid explosion
        }

    def _calculate_completeness_summary(self, quality_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall data completeness summary"""
        if not quality_metrics:
            return {"overall_completeness": "No data available"}
        
        total_records = 0
        total_null_records = 0
        field_completeness = {}
        
        for field_name, metrics in quality_metrics.items():
            if isinstance(metrics, dict) and "total_records" in metrics and "null_count" in metrics:
                field_total = metrics["total_records"] 
                field_nulls = metrics["null_count"]
                total_records += field_total
                total_null_records += field_nulls
                
                completeness_pct = ((field_total - field_nulls) / field_total * 100) if field_total > 0 else 0
                field_completeness[field_name] = {
                    "completeness_percentage": round(completeness_pct, 2),
                    "null_count": field_nulls,
                    "total_count": field_total
                }
        
        overall_completeness = ((total_records - total_null_records) / total_records * 100) if total_records > 0 else 0
        
        return {
            "overall_completeness_percentage": round(overall_completeness, 2),
            "field_level_completeness": field_completeness,
            "total_fields_analyzed": len(field_completeness)
        }

    def _calculate_uniqueness_summary(self, quality_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall data uniqueness summary"""
        if not quality_metrics:
            return {"overall_uniqueness": "No data available"}
        
        uniqueness_stats = {}
        
        for field_name, metrics in quality_metrics.items():
            if isinstance(metrics, dict) and "unique_values" in metrics and "total_records" in metrics:
                unique_count = metrics["unique_values"]
                total_count = metrics["total_records"]
                
                uniqueness_pct = (unique_count / total_count * 100) if total_count > 0 else 0
                uniqueness_stats[field_name] = {
                    "uniqueness_percentage": round(uniqueness_pct, 2),
                    "unique_values": unique_count,
                    "total_records": total_count,
                    "duplicate_records": total_count - unique_count
                }
        
        return uniqueness_stats

    async def _store_result_for_frontend(self, result: dict):
        """Store the metadata result for frontend access"""
        try:
            # Get the workflow ID from the workflow info
            workflow_id = workflow.info().workflow_id
            
            # Store result using an activity that can persist it
            await workflow.execute_activity_method(
                self.activities_cls.store_metadata_result,
                {"workflow_id": workflow_id, "result": result},
                start_to_close_timeout=timedelta(minutes=1)
            )
            logger.info(f"Metadata result stored successfully for frontend access with workflow ID: {workflow_id}")
        except Exception as e:
            logger.warning(f"Failed to store metadata result for frontend: {e}")
            # This is not critical, so we don't raise the exception

    def _log_metadata_results(self, result: dict):
        """Enhanced logging showcasing SourceSense's comprehensive metadata extraction"""
        logger.info("=" * 100)
        logger.info("🎯 NEOSENSE - INTELLIGENT NEO4J METADATA EXTRACTION")
        logger.info("   Advanced Graph Database Metadata Discovery & Analysis")
        logger.info("=" * 100)
        
        # Schema Information - Enhanced Display
        schema_info = result.get("Schema Information", {})
        logger.info("📊 SCHEMA DISCOVERY & ANALYSIS:")
        logger.info(f"   🏷️  Node Labels Discovered: {len(schema_info.get('node_labels', []))} types")
        for label in schema_info.get('node_labels', []):
            logger.info(f"      └─ {label}")
        logger.info(f"   🔗 Relationship Types: {len(schema_info.get('relationship_types', []))} types")
        for rel_type in schema_info.get('relationship_types', []):
            logger.info(f"      └─ {rel_type}")
        
        # Property Analysis
        prop_details = schema_info.get('node_property_details', {})
        total_properties = sum(len(props) for props in prop_details.values())
        logger.info(f"   📋 Property Analysis: {total_properties} properties across {len(prop_details)} node types")
        
        # Constraints & Indexes
        constraints = schema_info.get('constraints', [])
        indexes = schema_info.get('indexes', [])
        logger.info(f"   🔒 Data Integrity: {len(constraints)} constraints, {len(indexes)} indexes")
        for constraint in constraints:
            logger.info(f"      └─ {constraint.get('type', 'UNKNOWN')} constraint on {constraint.get('labelsOrTypes', ['Unknown'])}")
        
        # Business Context - Enhanced Analysis
        business_context = result.get("Business Context", {})
        logger.info("🏢 BUSINESS INTELLIGENCE & CONTEXT:")
        
        # Customer Analytics
        customer_segments = business_context.get('customer_segments', [])
        total_customers = sum(seg.get('customer_count', 0) for seg in customer_segments)
        premium_customers = sum(seg.get('customer_count', 0) for seg in customer_segments if seg.get('is_premium', False))
        logger.info(f"   👥 Customer Analytics: {total_customers} total customers")
        logger.info(f"      └─ Premium Customers: {premium_customers} ({(premium_customers/total_customers*100):.1f}%)" if total_customers > 0 else "      └─ Premium Customers: 0")
        
        # Product Catalog Analysis
        product_catalog = business_context.get('product_catalog', {})
        logger.info(f"   📦 Product Catalog: {product_catalog.get('total_products', 0)} products")
        if 'descriptions' in product_catalog:
            categories = set(p.get('category') for p in product_catalog['descriptions'] if p.get('category'))
            logger.info(f"      └─ Categories: {', '.join(categories)}")
        
        # Order Analytics
        order_stats = business_context.get('order_statistics', [])
        total_orders = sum(stat.get('order_count', 0) for stat in order_stats)
        logger.info(f"   📊 Order Analytics: {total_orders} total orders")
        for stat in order_stats:
            logger.info(f"      └─ {stat.get('order_status', 'Unknown')}: {stat.get('order_count', 0)} orders")
        
        # Graph Scale & Performance Metrics
        graph_stats = business_context.get('graph_statistics', {})
        if graph_stats:
            total_nodes = graph_stats.get('total_nodes', [{}])[0].get('count', 0)
            total_rels = graph_stats.get('total_relationships', [{}])[0].get('count', 0)
            logger.info(f"   📈 Graph Scale Metrics:")
            logger.info(f"      └─ Total Nodes: {total_nodes:,}")
            logger.info(f"      └─ Total Relationships: {total_rels:,}")
            logger.info(f"      └─ Graph Density: {(total_rels/max(total_nodes,1)):.2f} relationships per node")
        
        # Data Lineage & Flow Analysis
        lineage_info = result.get("Lineage Information", {})
        logger.info("🔗 DATA LINEAGE & FLOW ANALYSIS:")
        
        # Relationship Pattern Analysis
        patterns = lineage_info.get('relationship_patterns', {})
        logger.info(f"   🔄 Relationship Patterns: {patterns.get('total_patterns', 0)} unique patterns discovered")
        logger.info(f"   📊 Pattern Diversity: {patterns.get('unique_relationship_types', 0)} relationship types")
        
        # Data Flow Mapping
        data_flow = lineage_info.get('data_flow', {})
        entities = data_flow.get('entities', [])
        connections = data_flow.get('connections', [])
        logger.info(f"   🌐 Data Flow Network: {len(entities)} entities connected via {len(connections)} relationship types")
        
        # Graph Dependencies
        dependencies = lineage_info.get('graph_dependencies', [])
        logger.info(f"   🔗 Dependency Chains: {len(dependencies)} critical data dependencies identified")
        
        # Advanced Quality Analytics
        quality_metrics = result.get("Quality Metrics", {})
        completeness = quality_metrics.get('data_completeness', {})
        uniqueness = quality_metrics.get('data_uniqueness', {})
        
        logger.info("📈 ADVANCED QUALITY ANALYTICS:")
        logger.info(f"   ✅ Data Completeness Score: {completeness.get('overall_completeness_percentage', 0):.2f}%")
        logger.info(f"   🔍 Fields Analyzed: {completeness.get('total_fields_analyzed', 0)} properties")
        
        # Field-level quality breakdown
        field_completeness = completeness.get('field_level_completeness', {})
        if field_completeness:
            logger.info("   📋 Field-Level Quality Analysis:")
            for field, metrics in field_completeness.items():
                completeness_pct = metrics.get('completeness_percentage', 0)
                status = "🟢" if completeness_pct >= 90 else "🟡" if completeness_pct >= 70 else "🔴"
                logger.info(f"      {status} {field}: {completeness_pct:.1f}% complete")
        
        # Uniqueness Analysis
        if uniqueness:
            logger.info("   🎯 Data Uniqueness Analysis:")
            for field, metrics in uniqueness.items():
                uniqueness_pct = metrics.get('uniqueness_percentage', 0)
                status = "🟢" if uniqueness_pct >= 95 else "🟡" if uniqueness_pct >= 80 else "🔴"
                logger.info(f"      {status} {field}: {uniqueness_pct:.1f}% unique")
        
        logger.info("=" * 100)
        logger.info("✅ NEOSENSE METADATA EXTRACTION COMPLETED SUCCESSFULLY")
        logger.info("   🚀 Ready for Data Catalog Integration & Governance")
        logger.info("=" * 100)
        
        # Also log the full JSON for reference
        import json
        logger.info("📋 COMPLETE METADATA JSON:")
        logger.info(json.dumps(result, indent=2))
    
    @workflow.query
    async def get_metadata_result(self) -> dict:
        """Query method to retrieve the metadata result"""
        if self._metadata_result is None:
            return {"status": "running", "message": "Workflow is still processing"}
        return self._metadata_result

    @staticmethod
    def get_activities(activities: ActivitiesInterface) -> Sequence[Callable[..., Any]]:
        if not isinstance(activities, Neo4jActivities):
            raise TypeError("Activities must be an instance of Neo4jActivities")

        return [
            activities.get_workflow_args,
            activities.preflight_check,
            activities.fetch_node_labels,
            activities.fetch_relationship_types,
            activities.fetch_schema_info,
            activities.fetch_quality_and_context,
            activities.fetch_graph_statistics_and_indexes,
            activities.store_metadata_result,
        ]