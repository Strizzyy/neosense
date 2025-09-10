# app/workflow.py

import asyncio
from datetime import timedelta
from typing import Any, Dict, Sequence, Callable
from temporalio import workflow
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

    @workflow.query
    def get_metadata_result(self) -> dict | None:
        return self._metadata_result

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
            # Preflight check
            await workflow.execute_activity_method(
                self.activities_cls.preflight_check, 
                workflow_args, 
                start_to_close_timeout=timedelta(minutes=1),
            )

            # Execute all data gathering activities in parallel
            results = await asyncio.gather(
                workflow.execute_activity_method(
                    self.activities_cls.fetch_node_labels, 
                    workflow_args, 
                    start_to_close_timeout=timeout
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_relationship_types, 
                    workflow_args, 
                    start_to_close_timeout=timeout
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_schema_info, 
                    workflow_args, 
                    start_to_close_timeout=timeout
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_quality_and_context, 
                    workflow_args, 
                    start_to_close_timeout=timeout
                ),
                workflow.execute_activity_method(
                    self.activities_cls.fetch_graph_statistics_and_indexes, 
                    workflow_args, 
                    start_to_close_timeout=timeout
                )
            )

            labels, relationship_types, schema_info, quality_context, advanced_info = results
            
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
        ]