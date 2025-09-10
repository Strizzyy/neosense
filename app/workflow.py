"""
This file contains the workflow definition for the Neo4j metadata extraction application.
"""

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

# Standard setup for observability
logger = get_logger(__name__)
metrics = get_metrics()
traces = get_traces()

@workflow.defn
class Neo4jWorkflow(WorkflowInterface):
    def __init__(self):
        super().__init__()
        self._metadata_result: dict | None = None
        # --- FIX STARTS HERE (1) ---
        # Instantiate activities and assign to the attribute expected by the parent class.
        self.activities_cls = Neo4jActivities()
        # --- FIX ENDS HERE (1) ---

    @workflow.query
    def get_metadata_result(self) -> dict | None:
        """Allows querying the last successful result of the workflow."""
        return self._metadata_result

    @observability(logger=logger, metrics=metrics, traces=traces)
    @workflow.run
    async def run(self, workflow_config: Dict[str, Any]) -> dict:
        """
        Run the Neo4j metadata extraction workflow.
        """
        
        # --- FIX STARTS HERE (2) ---
        # Use the instance attribute defined in __init__ instead of creating a new local variable.
        # activities = Neo4jActivities()  <-- REMOVE THIS LINE
        # --- FIX ENDS HERE (2) ---
        timeout = timedelta(minutes=5)

        # 2. Get workflow args FIRST.
        workflow_args = await workflow.execute_activity_method(
            self.activities_cls.get_workflow_args, # Use the instance attribute
            workflow_config,
            start_to_close_timeout=timedelta(minutes=1),
        )
        
        try:
            # 3. Run a preflight check to ensure connectivity.
            await workflow.execute_activity_method(
                self.activities_cls.preflight_check, # Use the instance attribute
                workflow_args,
                start_to_close_timeout=timedelta(minutes=1),
            )

            # 4. Execute metadata fetching activities in parallel.
            logger.info("Starting parallel fetch of Neo4j metadata.")
            results = await asyncio.gather(
                workflow.execute_activity_method(self.activities_cls.fetch_node_labels, workflow_args, start_to_close_timeout=timeout),
                workflow.execute_activity_method(self.activities_cls.fetch_relationship_types, workflow_args, start_to_close_timeout=timeout),
                workflow.execute_activity_method(self.activities_cls.fetch_property_keys, workflow_args, start_to_close_timeout=timeout)
            )

            labels, rels, props = results
            logger.info(f"Successfully fetched {len(labels)} labels, {len(rels)} relationship types, and {len(props)} property keys.")

            self._metadata_result = {
                "node_labels": labels,
                "relationship_types": rels,
                "property_keys": props
            }

            return self._metadata_result
        finally:
            # 5. Call the parent's run method at the end to publish the final success event.
            # This call will now succeed because self.activities_cls exists.
            await super().run(workflow_config)

    @staticmethod
    def get_activities(activities: ActivitiesInterface) -> Sequence[Callable[..., Any]]:
        """Registers the activities with the SDK worker."""
        if not isinstance(activities, Neo4jActivities):
            raise TypeError("Activities must be an instance of Neo4jActivities")

        return [
            activities.get_workflow_args,
            activities.preflight_check,
            activities.fetch_node_labels,
            activities.fetch_relationship_types,
            activities.fetch_property_keys,
        ]