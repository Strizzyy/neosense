# � SolurceSense Neo4j

A metadata extraction application for Neo4j databases built using the Atlan Apps Framework. SourceSense connects to Neo4j databases and intelligently extracts schema information, business context, and metadata to help understand and manage your graph data.

![SourceSense Architecture](https://img.shields.io/badge/Neo4j-4.4+-blue) ![Atlan SDK](https://img.shields.io/badge/Atlan_SDK-0.1.1rc38-green) ![Python](https://img.shields.io/badge/Python-3.11+-blue)

## 🚀 Features

- **Schema Discovery**: Automatically extracts node labels, relationship types, and property keys
- **Connection Testing**: Built-in preflight checks to verify Neo4j connectivity
- **Parallel Processing**: Concurrent metadata extraction for optimal performance
- **Temporal Integration**: Reliable workflow orchestration with fault tolerance
- **Real-time Monitoring**: Track extraction progress through web interface

## 📋 Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Dapr CLI](https://docs.dapr.io/getting-started/install-dapr-cli/)
- [Temporal CLI](https://docs.temporal.io/cli)
- Neo4j Database (4.4+ recommended)

### Installation Guides
- [macOS Setup Guide](https://github.com/atlanhq/application-sdk/blob/main/docs/docs/setup/MAC.md)
- [Linux Setup Guide](https://github.com/atlanhq/application-sdk/blob/main/docs/docs/setup/LINUX.md)
- [Windows Setup Guide](https://github.com/atlanhq/application-sdk/blob/main/docs/docs/setup/WINDOWS.md)

## 🛠️ Quick Start

### 1. Setup Environment

```bash
# Clone and navigate to project
cd sourcesense-neo4j

# Install dependencies
uv sync

# Copy environment configuration
cp .env.example .env
```

### 2. Configure Neo4j Connection

Edit `.env` file with your Neo4j connection details:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### 3. Download Components

```bash
uv run poe download-components
```

### 4. Start Dependencies

In a separate terminal:
```bash
uv run poe start-deps
```

This starts:
- Dapr sidecar (port 3500)
- Temporal server (port 7233, UI at 8233)

### 5. Run SourceSense

```bash
uv run python main.py
```

**Access Points:**
- **SourceSense Web UI**: http://localhost:8000
- **Temporal UI**: http://localhost:8233
- **API Documentation**: http://localhost:8000/docs

## 📊 Extracted Metadata

SourceSense extracts the following metadata from your Neo4j database:

### Schema Information
- **Node Labels**: All unique node labels in the database
- **Relationship Types**: All relationship types and their directions
- **Property Keys**: All property keys used across nodes and relationships

### Sample Output
```json
{
  "node_labels": ["Person", "Company", "Product", "Order"],
  "relationship_types": ["WORKS_FOR", "PURCHASED", "MANUFACTURED_BY"],
  "property_keys": ["name", "email", "founded_date", "price", "quantity"]
}
```

## 🏗️ Architecture

SourceSense follows the Atlan Apps Framework architecture:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Interface │────│  Neo4jWorkflow   │────│  Neo4jActivities│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                │                        │
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Temporal Server │    │  Neo4jHandler   │
                       └──────────────────┘    └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │   Neo4jClient   │
                                               └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │ Neo4j Database  │
                                               └─────────────────┘
```

## 🔧 Development

### Project Structure
```
sourcesense-neo4j/
├── app/                    # Core application logic
│   ├── activities.py       # Temporal activities
│   ├── client.py          # Neo4j client wrapper
│   ├── handler.py         # Business logic
│   ├── workflow.py        # Workflow orchestration
│   └── queries/           # Cypher queries
│       ├── get_node_labels.cypher
│       ├── get_relationship_types.cypher
│       └── get_property_keys.cypher
├── deploy/                # Docker deployment
├── frontend/              # Web interface assets
├── tests/                 # Test files
├── main.py               # Application entry point
├── pyproject.toml        # Dependencies and config
└── README.md             # This file
```

### Running Tests
```bash
uv run pytest
```

### Stop Dependencies
```bash
uv run poe stop-deps
```

### Docker Deployment
```bash
# Build image
docker build -f deploy/Dockerfile -t sourcesense-neo4j .

# Run container
docker run -p 8000:8000 -e NEO4J_URI=bolt://host.docker.internal:7687 sourcesense-neo4j
```

## 🔍 Usage Examples

### Trigger Metadata Extraction

Via Web Interface:
1. Navigate to http://localhost:8000
2. Configure Neo4j connection details
3. Click "Extract Metadata"
4. Monitor progress in real-time

Via API:
```bash
curl -X POST "http://localhost:8000/api/v1/workflows" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_details": {
      "uri": "bolt://localhost:7687",
      "username": "neo4j",
      "password": "password"
    }
  }'
```

### Query Results
```bash
curl "http://localhost:8000/api/v1/workflows/{workflow_id}/result"
```

## 🛡️ Security Considerations

- Store Neo4j credentials securely using environment variables
- Use encrypted connections (bolt+s://) for production
- Implement proper authentication and authorization
- Regular security updates for dependencies

## 🤝 Contributing

We welcome contributions! Areas for enhancement:

- **Lineage Extraction**: Add relationship lineage mapping
- **Quality Metrics**: Implement data quality assessments
- **Advanced Metadata**: Extract constraints, indexes, and procedures
- **Multi-Database**: Support for Neo4j 4.0+ multi-database setups

## 📚 Learning Resources

- [Neo4j Documentation](https://neo4j.com/docs/)
- [Temporal Documentation](https://docs.temporal.io/)
- [Atlan Application SDK](https://github.com/atlanhq/application-sdk)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/)

## 📄 License

Apache-2.0 License - see LICENSE file for details.

---

Built with ❤️ using the Atlan Apps Framework