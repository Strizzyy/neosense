# SourceSense Neo4j: In-Depth Implementation Guide

## 1. Introduction

This document provides a comprehensive blueprint for building the SourceSense application for Neo4j using the Atlan Apps Framework. It is intended to guide the development process, ensuring the final application is robust, maintainable, and aligned with the framework's best practices.

## 2. High-Level Architecture

The application's architecture is designed to maximize modularity and leverage the strengths of the Atlan Apps Framework, particularly its separation of concerns between workflow orchestration and business logic.

```mermaid
graph TD
    subgraph "User & Orchestration"
        A[Workflow Trigger <br> (FastAPI or CLI)] --> B{Temporal Server};
        B -- "Assigns Task" --> C[Temporal Worker];
    end

    subgraph "Application Logic (Atlan App)"
        C -- "Runs" --> D[Neo4jWorkflow];
        D -- "Orchestrates" --> E[Neo4jActivities];
        E -- "Delegates to" --> F[Neo4jHandler];
        F -- "Uses" --> G[Neo4jClient];
    end

    subgraph "External System"
        G -- "Connects & Queries (Cypher)" --> H[(Neo4j Database)];
    end

    style D fill:#cde4ff
    style E fill:#cde4ff
    style F fill:#cde4ff
    style G fill:#cde4ff
```

## 3. Core Principles & Framework Context

This implementation will adhere to the core principles outlined in the Atlan Apps Framework documentation:

-   **Separation of Concerns:** Each component has a single, well-defined responsibility.
    -   **`Neo4jClient`**: Handles only the raw connection and query execution. This aligns with the `ClientInterface` concept. Since Neo4j is a NoSQL database, we will inherit from the base `ClientInterface` or `BaseClient` rather than the `BaseSQLClient`.
    -   **`Neo4jHandler`**: Contains all the business logic for *what* metadata to extract and *how*. This directly maps to the `HandlerInterface`'s role.
    -   **`Neo4jActivities`**: Acts as the durable, fault-tolerant entry point for individual tasks, as described in the `Activities` documentation. They are thin wrappers that make the handler's methods executable by a Temporal worker.
    -   **`Neo4jWorkflow`**: Defines the *sequence* and *flow* of operations, but not the implementation of those operations. This aligns perfectly with the `WorkflowInterface` concept.

-   **Configuration Driven:** The application will be configurable through environment variables, avoiding hardcoded credentials or connection details.

-   **Extensibility:** By building on the framework's base classes, the application can be easily extended in the future to extract more detailed metadata (e.g., lineage, quality metrics).

## 4. Detailed Component Implementation Plan

### a. Project Structure

Create the following directory structure to house the application components:

```
sourcesense_neo4j/
├── sourcesense/
│   ├── __init__.py
│   ├── app.py
│   ├── activities.py
│   ├── client.py
│   ├── handler.py
│   ├── workflow.py
│   └── queries/
│       ├── get_node_labels.cypher
│       ├── get_relationship_types.cypher
│       └── get_property_keys.cypher
├── .env.example
├── pyproject.toml
└── README.md
```

### b. `Neo4jClient` (`sourcesense/client.py`)

**Purpose:** To abstract the specifics of the `neo4j` driver and provide a clean interface for database interaction.

**Implementation:**

-   Inherit from `application_sdk.clients.ClientInterface`.
-   The `__init__` method will store connection parameters.
-   The `load` method will instantiate the `GraphDatabase.driver` and establish a connection.
-   A `close` method will handle driver cleanup.
-   A `run_query` method will execute a given Cypher query within a session, handle transaction management, and return the results as a list of records.

**Skeleton Code:**
```python
# sourcesense/client.py
from neo4j import GraphDatabase
from application_sdk.clients import ClientInterface

class Neo4jClient(ClientInterface):
    def __init__(self, uri, username, password):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None

    async def load(self):
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        await self.verify_connectivity()

    async def close(self):
        if self.driver:
            self.driver.close()

    async def verify_connectivity(self):
        # Corresponds to a simple query to ensure connection is valid
        self.driver.verify_connectivity()

    async def run_query(self, query: str, params: dict = None) -> list:
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
```

### c. `Neo4jHandler` (`sourcesense/handler.py`)

**Purpose:** To implement the core metadata extraction logic. This component is the "brains" of the operation.

**Implementation:**

-   Inherit from `application_sdk.handlers.HandlerInterface`.
-   The `__init__` will take a `Neo4jClient` instance.
-   `load`: Will call `load` on the client instance.
-   `test_auth`: Will use the client to run a simple query like `RETURN 1` to confirm valid credentials.
-   `preflight_check`: Will verify connectivity.
-   `fetch_metadata` methods: Each method will read a corresponding `.cypher` file from the `queries` directory, execute it using the `Neo4jClient`, and format the result.

**Skeleton Code:**
```python
# sourcesense/handler.py
import os
from application_sdk.handlers import HandlerInterface
from .client import Neo4jClient

class Neo4jHandler(HandlerInterface):
    def __init__(self, client: Neo4jClient):
        self.client = client

    async def load(self, **kwargs):
        await self.client.load()

    async def test_auth(self, **kwargs) -> bool:
        try:
            await self.client.run_query("RETURN 1")
            return True
        except Exception:
            return False

    # ... other interface methods ...

    async def get_node_labels(self) -> list[str]:
        query = self._read_query("get_node_labels.cypher")
        results = await self.client.run_query(query)
        return [item['label'] for item in results]

    # ... methods for relationships and properties ...

    def _read_query(self, filename: str) -> str:
        path = os.path.join(os.path.dirname(__file__), "queries", filename)
        with open(path, "r") as f:
            return f.read()
```

### d. `Neo4jActivities` (`sourcesense/activities.py`)

**Purpose:** To make the handler's methods available as fault-tolerant tasks for Temporal.

**Implementation:**

-   Inherit from `application_sdk.activities.ActivitiesInterface`.
-   The `__init__` will accept the `client_class` and `handler_class`.
-   The `_set_state` method will be overridden to instantiate the `Neo4jClient` and `Neo4jHandler` for a given workflow run.
-   Each activity will be a method that gets the state, calls the corresponding handler method, and returns the result. Use the `@activity.defn` decorator.

**Skeleton Code:**
```python
# sourcesense/activities.py
from temporalio import activity
from application_sdk.activities import ActivitiesInterface
from .client import Neo4jClient
from .handler import Neo4jHandler

class Neo4jActivities(ActivitiesInterface):
    # ... __init__ and state management ...

    @activity.defn
    async def fetch_node_labels(self, workflow_args: dict) -> list[str]:
        state = await self._get_state(workflow_args)
        return await state.handler.get_node_labels()

    # ... other activities for preflight, relationships, properties ...
```

### e. `Neo4jWorkflow` (`sourcesense/workflow.py`)

**Purpose:** To orchestrate the entire metadata extraction process in a reliable way.

**Implementation:**

-   Inherit from `application_sdk.workflows.WorkflowInterface`.
-   Point the `activities_cls` attribute to `Neo4jActivities`.
-   The static `get_activities` method will list all the activity methods that the worker needs to register.
-   The `run` method will define the execution flow:
    1.  Call the `preflight_check` activity.
    2.  Use `asyncio.gather` to run `fetch_node_labels`, `fetch_relationship_types`, and `fetch_property_keys` in parallel.
    3.  Collect and return the results in a structured dictionary.

**Skeleton Code:**
```python
# sourcesense/workflow.py
import asyncio
from temporalio import workflow
from application_sdk.workflows import WorkflowInterface
from .activities import Neo4jActivities

@workflow.defn
class Neo4jWorkflow(WorkflowInterface):
    activities_cls = Neo4jActivities

    @workflow.run
    async def run(self, workflow_config: dict) -> dict:
        # ... setup activities ...
        await workflow.execute_activity_method(self.activities_cls.preflight_check, ...)

        labels_future = workflow.execute_activity_method(self.activities_cls.fetch_node_labels, ...)
        rels_future = workflow.execute_activity_method(self.activities_cls.fetch_relationship_types, ...)
        props_future = workflow.execute_activity_method(self.activities_cls.fetch_property_keys, ...)

        labels, rels, props = await asyncio.gather(labels_future, rels_future, props_future)

        return {"node_labels": labels, "relationship_types": rels, "property_keys": props}
```

## 5. Development Roadmap

1.  **Setup Project**: Create the directory structure and `pyproject.toml` file with dependencies (`atlan-application-sdk`, `neo4j`, `uv`).
2.  **Implement Client**: Build `sourcesense/client.py`.
3.  **Create Cypher Queries**: Add `.cypher` files to `sourcesense/queries/`.
4.  **Implement Handler**: Build `sourcesense/handler.py`.
5.  **Implement Activities**: Build `sourcesense/activities.py`.
6.  **Implement Workflow**: Build `sourcesense/workflow.py`.
7.  **Build Application Entrypoint**: Create `sourcesense/app.py` to configure and run the worker.
8.  **Documentation**: Write the `README.md`.
