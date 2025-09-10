async function handleSubmit(event) {
    event.preventDefault();

    const runButton = document.getElementById("runWorkflowButton");
    runButton.disabled = true;
    runButton.innerHTML = '<span class="loading-spinner"></span>Extracting Metadata...';

    const payload = {};

    try {
        const startResponse = await fetch("/workflows/v1/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!startResponse.ok) throw new Error("Failed to start workflow");

        const responseData = await startResponse.json();
        console.log("Start response:", responseData);
        
        // Access the workflow_id from inside the nested 'data' object
        const workflowId = responseData.data?.workflow_id;

        if (!workflowId) {
            console.error("Could not find workflow ID in response:", responseData);
            throw new Error("Could not find data.workflow_id in the server response.");
        }

        const result = await pollForResult(workflowId);
        displayResults(result);

    } catch (error) {
        console.error("An error occurred:", error);
        showError("Failed to fetch metadata. Check the browser console and Docker logs for details.");
    } finally {
        runButton.disabled = false;
        runButton.textContent = "Fetch Metadata";
    }
}

async function pollForResult(workflowId, timeout = 30000) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeout) {
        try {
            const queryResponse = await fetch(`/workflows/v1/${workflowId}/query/get_metadata_result`);
            if (queryResponse.ok) {
                const result = await queryResponse.json();
                console.log("Polling result:", result);
                if (result && Object.keys(result).length > 0) return result;
            }
        } catch (error) { 
            console.warn("Polling failed, will retry...", error); 
        }
        await new Promise(resolve => setTimeout(resolve, 2000));
    }
    throw new Error("Polling timed out.");
}

function displayResults(data) {
    const resultsContainer = document.getElementById("results-container");
    const resultsContent = document.getElementById("results-content");

    if (!data || Object.keys(data).length === 0) {
        showError("No metadata results received");
        return;
    }

    // Extract the four main sections from your workflow response
    const schemaInfo = data["Schema Information"] || {};
    const businessContext = data["Business Context"] || {};
    const lineageInfo = data["Lineage Information"] || {};
    const qualityMetrics = data["Quality Metrics"] || {};

    resultsContent.innerHTML = `
        <div class="results-grid">
            <!-- Schema Information Section -->
            <div class="card result-section">
                <h3 class="schema-icon">Schema Information</h3>
                
                <div class="metadata-section">
                    <h4>Node Labels</h4>
                    <ul>
                        ${(schemaInfo.node_labels || []).map(label => 
                            `<li>${label}</li>`
                        ).join('') || '<li>No node labels found</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Relationship Types</h4>
                    <ul>
                        ${(schemaInfo.relationship_types || []).map(rel => 
                            `<li>${rel}</li>`
                        ).join('') || '<li>No relationships found</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Node Properties</h4>
                    <div class="expandable-content">
                        ${Object.entries(schemaInfo.node_property_details || {}).map(([label, props]) => 
                            `<div class="constraint-item">
                                <strong>${label}:</strong>
                                ${Object.entries(props).map(([prop, type]) => 
                                    `<div style="margin-left: 15px;">${prop} <span class="property-type">${type}</span></div>`
                                ).join('')}
                            </div>`
                        ).join('') || '<p>No property details found</p>'}
                    </div>
                </div>

                <div class="metadata-section">
                    <h4>Constraints & Indexes</h4>
                    <ul>
                        ${(schemaInfo.constraints || []).map(constraint => 
                            `<li class="constraint-item">
                                <strong>${constraint.name}</strong> - ${constraint.type}<br>
                                <small>Properties: ${(constraint.properties || []).join(', ')}</small>
                            </li>`
                        ).join('') || '<li>No constraints found</li>'}
                    </ul>
                </div>
            </div>

            <!-- Business Context Section -->
            <div class="card result-section">
                <h3 class="business-icon">Business Context</h3>
                
                <div class="metadata-section">
                    <h4>Graph Statistics</h4>
                    <ul>
                        ${businessContext.graph_statistics ? Object.entries(businessContext.graph_statistics).map(([key, value]) => {
                            if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
                                return `<li><strong>${key.replace(/_/g, ' ').toUpperCase()}:</strong><br>
                                    ${value.map(item => 
                                        `<div style="margin-left: 15px;">${Object.entries(item).map(([k,v]) => `${k}: ${v}`).join(', ')}</div>`
                                    ).join('')}</li>`;
                            }
                            return `<li><strong>${key.replace(/_/g, ' ').toUpperCase()}:</strong> ${JSON.stringify(value)}</li>`;
                        }).join('') : '<li>No graph statistics available</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Product Catalog</h4>
                    <ul>
                        ${(businessContext.product_catalog?.descriptions || []).map(product => 
                            `<li>
                                <strong>${product.product_name}</strong> - ${product.category}
                                <span class="metric-value">$${product.price}</span><br>
                                <small>${product.product_description}</small>
                            </li>`
                        ).join('') || '<li>No product information found</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Customer Segments</h4>
                    <ul>
                        ${(businessContext.customer_segments || []).map(segment => 
                            `<li>
                                ${segment.is_premium ? 'Premium' : 'Standard'} Customers: 
                                <span class="metric-value">${segment.customer_count}</span>
                            </li>`
                        ).join('') || '<li>No customer data found</li>'}
                    </ul>
                </div>
            </div>

            <!-- Lineage Information Section -->
            <div class="card result-section">
                <h3 class="lineage-icon">Lineage Information</h3>
                
                <div class="metadata-section">
                    <h4>Graph Dependencies</h4>
                    <ul>
                        ${(lineageInfo.graph_dependencies || []).map(dep => 
                            `<li>${dep}</li>`
                        ).join('') || '<li>No dependencies found</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Data Flow Entities</h4>
                    <ul>
                        ${(lineageInfo.data_flow?.entities || []).map(entity => 
                            `<li>${entity}</li>`
                        ).join('') || '<li>No entities found</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Connection Types</h4>
                    <ul>
                        ${(lineageInfo.data_flow?.connections || []).map(conn => 
                            `<li>${conn}</li>`
                        ).join('') || '<li>No connections found</li>'}
                    </ul>
                </div>
            </div>

            <!-- Quality Metrics Section -->
            <div class="card result-section">
                <h3 class="quality-icon">Quality Metrics</h3>
                
                <div class="metadata-section">
                    <h4>Data Completeness</h4>
                    <ul>
                        <li>
                            <strong>Overall Completeness:</strong> 
                            <span class="metric-value">${qualityMetrics.data_completeness?.overall_completeness_percentage || 'N/A'}%</span>
                        </li>
                        ${Object.entries(qualityMetrics.data_completeness?.field_level_completeness || {}).map(([field, metrics]) => 
                            `<li>
                                <strong>${field}:</strong> 
                                <span class="metric-value">${metrics.completeness_percentage}%</span>
                                <br><small>Null: ${metrics.null_count}/${metrics.total_count}</small>
                            </li>`
                        ).join('')}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Data Uniqueness</h4>
                    <ul>
                        ${Object.entries(qualityMetrics.data_uniqueness || {}).map(([field, metrics]) => 
                            `<li>
                                <strong>${field}:</strong> 
                                <span class="metric-value">${metrics.uniqueness_percentage}%</span>
                                <br><small>Unique: ${metrics.unique_values}/${metrics.total_records}</small>
                            </li>`
                        ).join('') || '<li>No uniqueness data available</li>'}
                    </ul>
                </div>

                <div class="metadata-section">
                    <h4>Field Quality Metrics</h4>
                    <ul>
                        ${Object.entries(qualityMetrics).filter(([key]) => !['data_completeness', 'data_uniqueness'].includes(key)).map(([field, metrics]) => {
                            if (typeof metrics === 'object' && metrics.metric_type) {
                                return `<li>
                                    <strong>${field}</strong> - ${metrics.metric_type}
                                    <br><small>Records: ${metrics.total_records}, Nulls: ${metrics.null_count}, Unique: ${metrics.unique_values}</small>
                                </li>`;
                            }
                            return '';
                        }).join('') || '<li>No field metrics available</li>'}
                    </ul>
                </div>
            </div>
        </div>
    `;

    resultsContainer.classList.remove("hidden");
}

function showError(message) {
    const resultsContainer = document.getElementById("results-container");
    const resultsContent = document.getElementById("results-content");
    
    resultsContent.innerHTML = `
        <div class="error-message">
            <strong>Error:</strong> ${message}
        </div>
    `;
    
    resultsContainer.classList.remove("hidden");
}