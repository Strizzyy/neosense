# Framework Notes - Interesting Challenges and Patterns

## Table of Contents
| S.No | Contents |
|------|----------|
| 1. | [Overview](#overview) |
| 2. | [Framework Integration Challenges](#framework-integration-challenges) |
|    | • [Async/Sync Bridge for Neo4j Driver](#challenge-1-asyncsync-bridge-for-neo4j-driver) |
|    | • [Dynamic Workflow Configuration](#challenge-2-dynamic-workflow-configuration) |
|    | • [Custom Route Integration with BaseApplication](#challenge-3-custom-route-integration-with-baseapplication) |
|    | • [Workflow Result Querying](#challenge-4-workflow-result-querying) |
| 3. | [Advanced Framework Patterns Discovered](#advanced-framework-patterns-discovered) |
|    | • [Parallel Activity Execution with Error Isolation](#pattern-1-parallel-activity-execution-with-error-isolation) |
|    | • [State Management in Activities](#pattern-2-state-management-in-activities) |
|    | • [Comprehensive Observability Integration](#pattern-3-comprehensive-observability-integration) |
| 4. | [Framework Contribution Opportunities](#framework-contribution-opportunities) |
|    | • [Enhanced Database Integration Support](#1-enhanced-database-integration-support) |
|    | • [Built-in Workflow Result Querying](#2-built-in-workflow-result-querying) |
|    | • [Dynamic Configuration Validation](#3-dynamic-configuration-validation) |
|    | • [Enhanced Error Context and Recovery](#4-enhanced-error-context-and-recovery) |

## Overview

This document details the interesting challenges encountered while working with Atlan's Apps Framework, the solutions implemented, and the patterns discovered that could benefit other developers and potentially enhance the framework itself.

## 🎯 Framework Integration Challenges

### Challenge 1: **Async/Sync Bridge for Neo4j Driver**

**Problem**: Neo4j's official Python driver is synchronous, but Atlan's Apps Framework requires async/await patterns throughout.

**Challenge Details**:
```python
# Neo4j driver is synchronous
with driver.session() as session:
    result = session.run(query)  # Blocking operation

# But Atlan SDK requires async patterns
async def run_query(self, query: str) -> List[Dict]:
    # How to bridge sync Neo4j with async framework?
```

**Solution Implemented**:
```python
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
```

**Key Insights**:
- Thread pool execution maintains async compatibility
- Proper error propagation from sync to async context
- Connection management requires careful lifecycle handling

**Framework Enhancement Opportunity**:
```python
# Suggested SDK enhancement for database integrations
class AsyncDatabaseClient(ClientInterface):
    async def execute_sync_operation(self, operation: Callable, *args, **kwargs):
        """Helper method for executing sync database operations in async context"""
        return await asyncio.get_event_loop().run_in_executor(
            None, operation, *args, **kwargs
        )
```

### Challenge 2: **Dynamic Workflow Configuration**

**Problem**: Atlan SDK workflows typically use static configuration, but NeoSense needs dynamic credential input from the frontend.

**Challenge Details**:
```python
# Traditional approach - static configuration
workflow_config = {
    "database_uri": os.environ.get("NEO4J_URI"),
    "username": os.environ.get("NEO4J_USERNAME")
}

# NeoSense requirement - dynamic credentials from user input
workflow_config = {
    "neo4j_credentials": {
        "neo4j_uri": user_provided_uri,
        "neo4j_username": user_provided_username,
        "neo4j_password": user_provided_password
    }
}
```

**Solution Implemented**:
```python
# Workflow receives dynamic configuration
@workflow.run
async def run(self, workflow_config: Dict[str, Any]) -> dict:
    """
    This function is the entry point for the workflow. It receives the workflow configuration,
    extracts the Neo4j credentials, and passes them to the activities.
    """
    # Extract dynamic credentials
    neo4j_credentials = workflow_config.get("neo4j_credentials", {})
    logger.info(f"Workflow started with credentials for: {neo4j_credentials.get('neo4j_uri')}")
    
    # Pass credentials through to activities
    workflow_args = await workflow.execute_activity_method(
        self.activities_cls.get_workflow_args,
        {**workflow_config, "neo4j_credentials": neo4j_credentials}
    )

# Activities handle both dynamic and static credentials
async def _setup_state_if_needed(self, workflow_args: dict) -> None:
    """
    This function sets up the state for the activities. It first tries to get the credentials
    from the workflow arguments. If the credentials are not found in the workflow arguments,
    it falls back to the environment variables.
    """
    credentials = workflow_args.get("neo4j_credentials", {})
    
    # Dynamic credentials (preferred) or environment fallback
    uri = credentials.get("neo4j_uri") or os.environ.get("NEO4J_URI")
    username = credentials.get("neo4j_username") or os.environ.get("NEO4J_USERNAME")
    password = credentials.get("neo4j_password") or os.environ.get("NEO4J_PASSWORD")
```

**Key Insights**:
- The workflow configuration can be extended to accept dynamic credentials from the frontend.
- The get_workflow_args activity is used to extract the credentials from the workflow configuration and pass them to the other activities.
- The activities first try to get the credentials from the workflow arguments. If the credentials are not found in the workflow arguments, they fall back to the environment variables.

**Framework Enhancement Opportunity**:
```python
# Suggested SDK enhancement for dynamic configuration
class DynamicWorkflowInterface(WorkflowInterface):
    def validate_dynamic_config(self, config: Dict[str, Any]) -> bool:
        """Validate dynamic configuration before workflow execution"""
        pass
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON schema for expected configuration"""
        pass
```

### Challenge 3: **Custom Route Integration with BaseApplication**

**Problem**: Atlan's BaseApplication sets up a FastAPI server, but accessing it to add custom routes is not straightforward.

**Challenge Details**:
```python
# BaseApplication creates FastAPI server internally
app = BaseApplication(name=APPLICATION_NAME)
await app.setup_server(workflow_class=Neo4jWorkflow)

# But how to access the FastAPI instance to add custom routes?
# app.fastapi_app?  # Not available
# app.server?       # Not documented
# app._server?      # Private attribute
```

**Solution Implemented**:
```python
# Dynamic FastAPI app discovery
fastapi_app = None
possible_attrs = ['server_app', 'app', '_app', 'fastapi_app', 'server', '_server']

for attr in possible_attrs:
    if hasattr(app, attr):
        potential_app = getattr(app, attr)
        logger.info(f"Checking attribute {attr}: {type(potential_app)}")
        if potential_app and hasattr(potential_app, 'add_api_route'):
            fastapi_app = potential_app
            logger.info(f"Found FastAPI app via {attr}")
            break

# Custom route registration with error handling
if fastapi_app:
    try:
        fastapi_app.add_api_route(
            "/api/test-connection",
            test_connection_handler,
            methods=["POST"]
        )
        logger.info("Successfully registered custom routes")
    except Exception as e:
        logger.error(f"Route registration failed: {e}")
```

**Key Insights**:
- BaseApplication's FastAPI instance is accessible but not well-documented
- Custom route registration requires defensive programming
- Multiple fallback strategies ensure robustness

**Framework Enhancement Opportunity**:
```python
# Suggested SDK enhancement for custom routes
class BaseApplication:
    def get_fastapi_app(self) -> FastAPI:
        """Get the FastAPI application instance for custom route registration"""
        return self._fastapi_app
    
    def add_custom_routes(self, router: APIRouter):
        """Add custom routes to the application"""
        self._fastapi_app.include_router(router)
```

### Challenge 4: **Workflow Result Querying**

**Problem**: Atlan SDK doesn't provide built-in mechanisms for querying workflow results in real-time.

**Challenge Details**:
```python
# Workflow executes and completes
workflow_result = await workflow.run(config)

# But how does the frontend get the result?
# No built-in query endpoints
# No real-time result streaming
# No workflow status monitoring
```

**Solution Implemented**:
```python
# Custom result storage and retrieval
@activity.defn
async def store_metadata_result(self, data: Dict[str, Any]) -> bool:
    """
    This activity stores the metadata result for frontend access. It receives the workflow ID and the result,
    and stores the result in a JSON file. It also stores the latest result as "latest.json" for easy access.
    """
    try:
        workflow_id = data.get("workflow_id")
        result = data.get("result")
        
        # File-based storage for persistence
        results_dir = "workflow_results"
        os.makedirs(results_dir, exist_ok=True)
        
        result_file = os.path.join(results_dir, f"{workflow_id}.json")
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Also store as latest for easy access
        latest_file = os.path.join(results_dir, "latest.json")
        with open(latest_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Failed to store metadata result: {e}")
        return False

# Custom API endpoint for result retrieval
@fastapi_app.get("/api/workflow-result/{workflow_id}")
async def get_workflow_result(workflow_id: str):
    """
    This API endpoint retrieves the workflow result from file storage. It receives the workflow ID,
    and returns the result in JSON format.
    """
    results_dir = "workflow_results"
    result_file = os.path.join(results_dir, f"{workflow_id}.json")
    
    if os.path.exists(result_file):
        with open(result_file, 'r') as f:
            return json.load(f)
    
    raise HTTPException(status_code=404, detail="Workflow result not found")
```

**Key Insights**:
- The workflow results are stored in a file-based storage for persistence across application restarts.
- A custom API endpoint is provided to bridge the workflow results to the frontend.
- The store_metadata_result activity is used to store the workflow results in a JSON file.

**Framework Enhancement Opportunity**:
```python
# Suggested SDK enhancement for workflow querying
@workflow.defn
class WorkflowInterface:
    @workflow.query
    async def get_result(self) -> Dict[str, Any]:
        """Built-in query method for retrieving workflow results"""
        return self._result
    
    @workflow.query
    async def get_status(self) -> Dict[str, Any]:
        """Get current workflow status and progress"""
        return {
            "status": self._status,
            "progress": self._progress,
            "completed_activities": self._completed_activities
        }
```

## 🔧 Advanced Framework Patterns Discovered

### Pattern 1: **Parallel Activity Execution with Error Isolation**

**Discovery**: Using `asyncio.gather` with `return_exceptions=True` provides excellent error isolation while maintaining performance.

```python
# Advanced parallel execution pattern
results = await asyncio.gather(
    workflow.execute_activity_method(self.activities_cls.fetch_node_labels, ...),
    workflow.execute_activity_method(self.activities_cls.fetch_relationship_types, ...),
    workflow.execute_activity_method(self.activities_cls.fetch_schema_info, ...),
    workflow.execute_activity_method(self.activities_cls.fetch_quality_and_context, ...),
    workflow.execute_activity_method(self.activities_cls.fetch_graph_statistics_and_indexes, ...),
    return_exceptions=True  # Key insight: isolate failures
)

# Intelligent error handling
successful_results = [r for r in results if not isinstance(r, Exception)]
failed_activities = [r for r in results if isinstance(r, Exception)]

if failed_activities:
    logger.warning(f"Some activities failed: {len(failed_activities)}. Proceeding with partial results.")
    # Continue with partial results rather than failing completely
```

**Benefits**:
- Performance improvement over sequential execution
- Graceful degradation when some activities fail
- Detailed error reporting for debugging

### Pattern 2: **State Management in Activities**

**Discovery**: Lazy initialization with connection reuse provides optimal resource management.

```python
class Neo4jActivities(ActivitiesInterface):
    def __init__(self):
        self.handler: Neo4jHandler | None = None  # Lazy initialization
    
    async def _setup_state_if_needed(self, workflow_args: dict) -> None:
        """Initialize handler only when needed, reuse across activities"""
        if self.handler is None:
            # Create connection and handler
            client = Neo4jClient(uri=uri, username=username, password=password)
            self.handler = Neo4jHandler(client=client)
            await self.handler.load()
    
    @activity.defn
    async def fetch_node_labels(self, workflow_args: dict) -> list[str]:
        await self._setup_state_if_needed(workflow_args)  # Reuse connection
        return await self.handler.get_node_labels()
```

**Benefits**:
- Efficient resource usage (single connection per workflow)
- Automatic cleanup when workflow completes
- Thread-safe state management

### Pattern 3: **Comprehensive Observability Integration**

**Discovery**: Structured logging with business context provides excellent debugging and monitoring.

```python
@observability(logger=logger, metrics=metrics, traces=traces)
async def run(self, workflow_config: Dict[str, Any]) -> dict:
    # Business-context logging
    logger.info("🎯 NEOSENSE - INTELLIGENT NEO4J METADATA EXTRACTION")
    logger.info("   Advanced Graph Database Metadata Discovery & Analysis")
    
    # Progress tracking
    logger.info("Starting parallel metadata extraction activities")
    
    # Results logging with metrics
    logger.info(f"   📊 Processing {total_nodes} nodes, {total_relationships} relationships")
    logger.info(f"   ✅ Data Quality Score: {quality_score:.2f}%")
    logger.info(f"   🏢 Business Intelligence: {len(customer_segments)} segments discovered")
```

**Benefits**:
- Rich debugging information
- Business metrics in logs
- Production monitoring capabilities

## 🚀 Framework Contribution Opportunities

### 1. **Enhanced Database Integration Support**

**Current Gap**: No standardized patterns for integrating synchronous database drivers with async workflows.

**Proposed Enhancement**:
```python
# New base class for database integrations
class AsyncDatabaseActivities(ActivitiesInterface):
    def __init__(self, client_class: Type[ClientInterface], handler_class: Type[HandlerInterface]):
        self.client_class = client_class
        self.handler_class = handler_class
        self._handler = None
    
    async def _get_handler(self, workflow_args: dict) -> HandlerInterface:
        if self._handler is None:
            config = self._extract_connection_config(workflow_args)
            client = self.client_class(**config)
            self._handler = self.handler_class(client=client)
            await self._handler.load()
        return self._handler
    
    async def execute_sync_operation(self, operation: Callable, *args, **kwargs):
        """Helper for executing sync database operations in async context"""
        return await asyncio.get_event_loop().run_in_executor(None, operation, *args, **kwargs)
```

### 2. **Built-in Workflow Result Querying**

**Current Gap**: No standard way to query workflow results or monitor progress.

**Proposed Enhancement**:
```python
# Enhanced workflow interface with querying support
@workflow.defn
class QueryableWorkflowInterface(WorkflowInterface):
    def __init__(self):
        super().__init__()
        self._result: Dict[str, Any] = {}
        self._progress: Dict[str, Any] = {}
        self._status: str = "initializing"
    
    @workflow.query
    async def get_result(self) -> Dict[str, Any]:
        """Get the current workflow result"""
        return self._result
    
    @workflow.query
    async def get_progress(self) -> Dict[str, Any]:
        """Get current workflow progress"""
        return self._progress
    
    @workflow.signal
    async def update_progress(self, progress: Dict[str, Any]):
        """Update workflow progress (called by activities)"""
        self._progress.update(progress)
```

### 3. **Dynamic Configuration Validation**

**Current Gap**: No built-in validation for dynamic workflow configuration.

**Proposed Enhancement**:
```python
# Configuration validation support
class ConfigurableWorkflowInterface(WorkflowInterface):
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for workflow configuration"""
        return {
            "type": "object",
            "properties": {
                "database_credentials": {
                    "type": "object",
                    "required": ["uri", "username", "password"]
                }
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate configuration against schema"""
        # Implementation using jsonschema
        pass
```

### 4. **Enhanced Error Context and Recovery**

**Current Gap**: Limited error context and recovery suggestions.

**Proposed Enhancement**:
```python
# Enhanced error handling with recovery suggestions
class EnhancedActivityError(Exception):
    def __init__(self, message: str, context: Dict[str, Any], recovery_suggestions: List[str]):
        super().__init__(message)
        self.context = context
        self.recovery_suggestions = recovery_suggestions
        self.error_code = self._generate_error_code()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": str(self),
            "context": self.context,
            "recovery_suggestions": self.recovery_suggestions,
            "timestamp": datetime.utcnow().isoformat()
        }

# Usage in activities
@activity.defn
async def fetch_metadata(self, args: dict) -> dict:
    try:
        return await self.handler.extract_metadata()
    except ConnectionError as e:
        raise EnhancedActivityError(
            message="Database connection failed",
            context={
                "database_uri": self.client.uri,
                "connection_timeout": self.client.timeout,
                "retry_count": args.get("retry_count", 0)
            },
            recovery_suggestions=[
                "Verify database is running and accessible",
                "Check network connectivity",
                "Validate connection credentials",
                "Increase connection timeout if network is slow"
            ]
        )
