async function handleSubmit(event) {
    event.preventDefault();

    const runButton = document.getElementById("runWorkflowButton");
    runButton.disabled = true;
    runButton.textContent = "Fetching...";

    const payload = {};

    try {
        const startResponse = await fetch("/workflows/v1/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!startResponse.ok) throw new Error("Failed to start workflow");

        const responseData = await startResponse.json();
        
        // --- THIS IS THE FINAL FIX ---
        // Access the workflow_id from inside the nested 'data' object.
        const workflowId = responseData.data.workflow_id;
        // --- END OF FIX ---

        if (!workflowId) {
            console.error("Could not find workflow ID in response:", responseData);
            throw new Error("Could not find data.workflow_id in the server response.");
        }

        const result = await pollForResult(workflowId);
        displayResults(result);

    } catch (error) {
        console.error("An error occurred:", error);
        alert("Failed to fetch metadata. Check the browser console and Docker logs for details.");
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
                if (result) return result;
            }
        } catch (error) { console.warn("Polling failed, will retry...", error); }
        await new Promise(resolve => setTimeout(resolve, 2000));
    }
    throw new Error("Polling timed out.");
}

function displayResults(data) {
    const resultsContainer = document.getElementById("results-container");
    const resultsContent = document.getElementById("results-content");

    resultsContent.innerHTML = `
        <div class="result-section">
            <h3>Node Labels</h3>
            <ul>${(data.node_labels || []).map(item => `<li>${item}</li>`).join('') || '<li>None found</li>'}</ul>
        </div>
        <div class="result-section">
            <h3>Relationship Types</h3>
            <ul>${(data.relationship_types || []).map(item => `<li>${item}</li>`).join('') || '<li>None found</li>'}</ul>
        </div>
        <div class="result-section">
            <h3>Property Keys</h3>
            <ul>${(data.property_keys || []).map(item => `<li>${item}</li>`).join('') || '<li>None found</li>'}</ul>
        </div>
    `;
    resultsContainer.classList.remove("hidden");
}