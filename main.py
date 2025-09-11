import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.activities import Neo4jActivities
from app.workflow import Neo4jWorkflow
from application_sdk.application import BaseApplication
from application_sdk.observability.decorators.observability_decorator import (
    observability,
)
from application_sdk.observability.logger_adaptor import get_logger
from application_sdk.observability.metrics_adaptor import get_metrics
from application_sdk.observability.traces_adaptor import get_traces

logger = get_logger(__name__)
metrics = get_metrics()
traces = get_traces()

APPLICATION_NAME = "neosense"

@observability(logger=logger, metrics=metrics, traces=traces)
async def main():
    logger.info("Starting NeoSense application")
    app = BaseApplication(name=APPLICATION_NAME)

    await app.setup_workflow(
        workflow_and_activities_classes=[(Neo4jWorkflow, Neo4jActivities)],
    )

    await app.start_worker()
    
    await app.setup_server(workflow_class=Neo4jWorkflow)
    logger.info("Base server setup is complete.")
    
    # Try to access the FastAPI app through different possible attributes
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
            elif potential_app and hasattr(potential_app, 'get'):
                # Might be a FastAPI app
                fastapi_app = potential_app
                logger.info(f"Found potential FastAPI app via {attr}")
                break
    
    if fastapi_app:
        setup_frontend_routes(fastapi_app)
    else:
        logger.warning("Could not find FastAPI app instance - routes will not be available")
        # Print all available attributes for debugging
        logger.info(f"Available attributes: {[attr for attr in dir(app) if not attr.startswith('_')]}")
    
    await app.start_server()

def setup_frontend_routes(fastapi_app):
    """Setup frontend routes"""
    logger.info("=== SETTING UP FRONTEND ROUTES ===")
    logger.info(f"FastAPI app type: {type(fastapi_app)}")
    
    # Simple in-memory storage for workflow results
    workflow_results = {}
    
    from fastapi import HTTPException
    import json
    import os
    
    # API Routes
    @fastapi_app.get("/api/workflow-result/{workflow_id}")
    async def get_workflow_result(workflow_id: str):
        """Get workflow result from file storage or memory"""
        logger.info(f"Checking for workflow result: {workflow_id}")
        
        # First check in-memory storage
        if workflow_id in workflow_results:
            logger.info("Found workflow result in memory!")
            return workflow_results[workflow_id]
        
        # Then check file storage
        results_dir = "workflow_results"
        result_file = os.path.join(results_dir, f"{workflow_id}.json")
        
        if os.path.exists(result_file):
            try:
                with open(result_file, 'r') as f:
                    result = json.load(f)
                logger.info("Found workflow result in file storage!")
                return result
            except Exception as e:
                logger.error(f"Error reading result file: {e}")
        
        # Finally check for latest result
        latest_file = os.path.join(results_dir, "latest.json")
        if os.path.exists(latest_file):
            try:
                with open(latest_file, 'r') as f:
                    result = json.load(f)
                logger.info("Found latest workflow result!")
                return result
            except Exception as e:
                logger.error(f"Error reading latest result file: {e}")
        
        logger.info("Workflow result not ready yet")
        raise HTTPException(status_code=404, detail="Workflow not ready")
    
    @fastapi_app.post("/api/store-result/{workflow_id}")
    async def store_workflow_result(workflow_id: str, result: dict):
        """Store workflow result (this will be called by our workflow)"""
        logger.info(f"Storing result for workflow: {workflow_id}")
        workflow_results[workflow_id] = result
        return {"status": "stored"}
    
    @fastapi_app.get("/test/metadata")
    async def test_metadata():
        """Real metadata extracted from Neo4j workflow"""
        return {
            "Business Context": {
                "customer_segments": [
                    {"customer_count": 2, "is_premium": True},
                    {"customer_count": 2, "is_premium": False}
                ],
                "graph_statistics": {
                    "node_counts_by_label": [
                        {"count": 5, "label": "Product"},
                        {"count": 4, "label": "Customer"},
                        {"count": 4, "label": "Order"},
                        {"count": 3, "label": "Category"},
                        {"count": 2, "label": "Supplier"}
                    ],
                    "relationship_counts_by_type": [
                        {"count": 5, "type": "BELONGS_TO"},
                        {"count": 5, "type": "CONTAINS"},
                        {"count": 4, "type": "PLACED_ORDER"},
                        {"count": 3, "type": "SUPPLIES"}
                    ],
                    "total_nodes": [{"count": 18}],
                    "total_relationships": [{"count": 17}]
                },
                "order_statistics": [
                    {"order_count": 1, "order_status": "Shipped"},
                    {"order_count": 1, "order_status": "Processing"},
                    {"order_count": 1, "order_status": "Delivered"},
                    {"order_count": 1, "order_status": "Cancelled"}
                ],
                "product_catalog": {
                    "descriptions": [
                        {"category": "Office Supplies", "price": 12.99, "product_description": "Ceramic coffee mug with company logo.", "product_name": "Coffee Mug"},
                        {"category": "Electronics", "price": 1299.99, "product_description": "High-performance laptop for professionals and creatives.", "product_name": "MacBook Pro"},
                        {"category": "Electronics", "price": 79.99, "product_description": "Multi-port USB-C hub with HDMI and ethernet.", "product_name": "USB-C Hub"},
                        {"category": "Electronics", "price": 29.99, "product_description": "Ergonomic wireless mouse with precision tracking.", "product_name": "Wireless Mouse"}
                    ],
                    "total_products": 4
                }
            },
            "Lineage Information": {
                "data_flow": {
                    "connections": ["BELONGS_TO", "CONTAINS", "PLACED_ORDER", "SUPPLIES"],
                    "entities": ["Category", "Customer", "Order", "Product", "Supplier"],
                    "potential_flows": [
                        "Category -> BELONGS_TO -> Customer",
                        "Category -> CONTAINS -> Customer",
                        "Category -> PLACED_ORDER -> Customer",
                        "Category -> SUPPLIES -> Customer",
                        "Category -> BELONGS_TO -> Order",
                        "Category -> CONTAINS -> Order",
                        "Category -> PLACED_ORDER -> Order",
                        "Category -> SUPPLIES -> Order",
                        "Category -> BELONGS_TO -> Product",
                        "Category -> CONTAINS -> Product"
                    ]
                },
                "graph_dependencies": [
                    "(:Customer)-[:PLACED_ORDER]->(:Order)",
                    "(:Order)-[:CONTAINS]->(:Product)",
                    "(:Product)-[:BELONGS_TO]->(:Category)",
                    "(:Supplier)-[:SUPPLIES]->(:Product)"
                ],
                "relationship_patterns": {
                    "patterns": [
                        "(:Customer)-[:PLACED_ORDER]->(:Order)",
                        "(:Order)-[:CONTAINS]->(:Product)",
                        "(:Product)-[:BELONGS_TO]->(:Category)",
                        "(:Supplier)-[:SUPPLIES]->(:Product)"
                    ],
                    "patterns_by_relationship_type": {
                        "BELONGS_TO": ["(:Product)-[:BELONGS_TO]->(:Category)"],
                        "CONTAINS": ["(:Order)-[:CONTAINS]->(:Product)"],
                        "PLACED_ORDER": ["(:Customer)-[:PLACED_ORDER]->(:Order)"],
                        "SUPPLIES": ["(:Supplier)-[:SUPPLIES]->(:Product)"]
                    },
                    "total_patterns": 4,
                    "unique_relationship_types": 4
                }
            },
            "Quality Metrics": {
                "Customer.email": {
                    "metric_type": "Null Count",
                    "null_count": 1,
                    "total_records": 4,
                    "unique_values": 3
                },
                "Order.status": {
                    "metric_type": "Completeness",
                    "null_count": 0,
                    "total_records": 4,
                    "unique_values": 4
                },
                "Product.category": {
                    "metric_type": "Uniqueness",
                    "null_count": 0,
                    "total_records": 5,
                    "unique_values": 3
                },
                "data_completeness": {
                    "field_level_completeness": {
                        "Customer.email": {
                            "completeness_percentage": 75,
                            "null_count": 1,
                            "total_count": 4
                        },
                        "Order.status": {
                            "completeness_percentage": 100,
                            "null_count": 0,
                            "total_count": 4
                        },
                        "Product.category": {
                            "completeness_percentage": 100,
                            "null_count": 0,
                            "total_count": 5
                        }
                    },
                    "overall_completeness_percentage": 92.31,
                    "total_fields_analyzed": 3
                },
                "data_uniqueness": {
                    "Customer.email": {
                        "duplicate_records": 1,
                        "total_records": 4,
                        "unique_values": 3,
                        "uniqueness_percentage": 75
                    },
                    "Order.status": {
                        "duplicate_records": 0,
                        "total_records": 4,
                        "unique_values": 4,
                        "uniqueness_percentage": 100
                    },
                    "Product.category": {
                        "duplicate_records": 2,
                        "total_records": 5,
                        "unique_values": 3,
                        "uniqueness_percentage": 60
                    }
                }
            },
            "Schema Information": {
                "constraints": [
                    {"labelsOrTypes": ["Customer"], "name": "customer_email_unique", "properties": ["email"], "type": "UNIQUENESS"},
                    {"labelsOrTypes": ["Order"], "name": "order_id_unique", "properties": ["orderId"], "type": "UNIQUENESS"},
                    {"labelsOrTypes": ["Product"], "name": "product_id_unique", "properties": ["productId"], "type": "UNIQUENESS"}
                ],
                "indexes": [
                    {"labelsOrTypes": ["Customer"], "name": "customer_email_unique", "properties": ["email"], "type": "RANGE"},
                    {"labelsOrTypes": ["Customer"], "name": "customer_name_index", "properties": ["name"], "type": "RANGE"},
                    {"labelsOrTypes": None, "name": "index_343aff4e", "properties": None, "type": "LOOKUP"},
                    {"labelsOrTypes": None, "name": "index_f7700477", "properties": None, "type": "LOOKUP"},
                    {"labelsOrTypes": ["Order"], "name": "order_id_unique", "properties": ["orderId"], "type": "RANGE"},
                    {"labelsOrTypes": ["Order"], "name": "order_status_index", "properties": ["status"], "type": "RANGE"},
                    {"labelsOrTypes": ["Product"], "name": "product_category_index", "properties": ["category"], "type": "RANGE"},
                    {"labelsOrTypes": ["Product"], "name": "product_id_unique", "properties": ["productId"], "type": "RANGE"}
                ],
                "node_labels": ["Category", "Customer", "Order", "Product", "Supplier"],
                "node_property_details": {
                    "Category": {"description": "STRING", "name": "STRING"},
                    "Customer": {"age": "INTEGER", "city": "STRING", "customerId": "STRING", "email": "STRING", "isPremium": "BOOLEAN", "name": "STRING", "signupDate": "STRING"},
                    "Order": {"orderDate": "STRING", "orderId": "STRING", "shippingAddress": "STRING", "status": "STRING", "totalAmount": "FLOAT"},
                    "Product": {"brand": "STRING", "category": "STRING", "description": "STRING", "name": "STRING", "price": "FLOAT", "productId": "STRING", "rating": "FLOAT", "stock": "INTEGER"},
                    "Supplier": {"country": "STRING", "name": "STRING", "supplierId": "STRING"}
                },
                "relationship_types": ["BELONGS_TO", "CONTAINS", "PLACED_ORDER", "SUPPLIES"]
            }
        }
    
    # Frontend routes
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        logger.warning("Frontend directory not found.")
        return
    
    # Mount static files
    static_dir = frontend_dir / "static"
    if static_dir.exists():
        fastapi_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Setup templates
    templates_dir = frontend_dir / "templates"
    if templates_dir.exists():
        templates = Jinja2Templates(directory=str(templates_dir))
        
        @fastapi_app.get("/", response_class=HTMLResponse)
        async def home(request: Request):
            return templates.TemplateResponse("index.html", {"request": request})
        
        @fastapi_app.get("/favicon.ico")
        async def favicon():
            return {"message": "No favicon"}
    
    # Make the storage accessible to the workflow
    fastapi_app.workflow_results = workflow_results
    
    logger.info("Frontend routes setup completed successfully")

if __name__ == "__main__":
    asyncio.run(main())