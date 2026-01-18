const form = document.getElementById("fit-form");
const progressContainer = document.getElementById("progress-container");
const progressBar = document.getElementById("progress-bar");
const statusText = document.getElementById("status-text");
const resultsDiv = document.getElementById("results");
const totalsDiv = document.getElementById("totals");

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Save the current textarea value and checkbox state before processing
    const textarea = document.querySelector('textarea[name="fitting"]');
    const savedInput = textarea.value;
    const includeHullCheckbox = document.querySelector('input[name="include_hull"]');
    const savedChecked = includeHullCheckbox.checked;

    // Reset UI
    progressContainer.style.display = "block";
    progressBar.value = 0;
    statusText.textContent = "Starting...";
    resultsDiv.innerHTML = "";
    totalsDiv.innerHTML = "";  // Clear totals as well for consistency

    const formData = new FormData(form);

    const response = await fetch("/stream", {
        method: "POST",
        body: formData
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
            if (!line.trim()) continue;
            const msg = JSON.parse(line);

            if (msg.type === "progress") {
                progressBar.value = (msg.current / msg.total) * 100;
                statusText.textContent = `Processing ${msg.current} / ${msg.total}: ${msg.item}`;
            }

            else if (msg.type === "done") {
                console.log("DONE event received:", msg);
                progressBar.value = 100;
                statusText.textContent = "Done!";
                renderResults(msg.parsed, msg.totals);
            }

            else if (msg.type === "error") {
                statusText.textContent = `Error: ${msg.message}`;
                console.error(msg.message);
            }
        }

        if (done && buffer.trim()) {
            const msg = JSON.parse(buffer);
            if (msg.type === "done") {
                progressBar.value = 100;
                statusText.textContent = "Done!";
                finalParsed = msg.parsed;
                finalTotals = msg.totals;
                console.log("Sending parsed as", finalParsed)
                console.log("Sending totals as", finalTotals)
                renderResults(finalParsed, finalTotals);
            }
            else if (msg.type === "error") {
                statusText.textContent = `Error: ${msg.message}`;
                console.error(msg.message);
            }
        }

        if (done) break;
    }
});

function renderResults(finalParsed, finalTotals) {
    const totalsDiv = document.getElementById("totals");

    console.log("renderResults called with", finalParsed);
    console.log("renderResults totals:", finalTotals);

    let html = "<h2>Parsed Fitting</h2>";

    if (finalTotals) {
        totalsDiv.innerHTML = `
        <h2>Totals</h2>
        <table>
            <tr><th>Total Volume</th><td>${finalTotals.volume.toLocaleString()}</td></tr>
            <tr><th>Jita Market Price</th><td>${Math.round(finalTotals.subtotal_jita).toLocaleString()}</td></tr>
            <tr><th>C-J6MT Market Price</th><td>${Math.round(finalTotals.subtotal_gsf).toLocaleString()}</td></tr>
            <tr><th>Minimum Obtainable Price</th><td>${Math.round(finalTotals.min_price).toLocaleString()}</td></tr>
            <tr><th>Marked Up Price (+${finalTotals.markup_pct}%)</th><td>${Math.round(finalTotals.marked_up_price).toLocaleString()}</td></tr>
        </table>
    `;
    }

    for (const [section, items] of Object.entries(finalParsed)) {
        html += `<h3>${section}</h3><table>`;
        html += `
        <tr>
            <th>Name</th>
            <th>Qty</th>
            <th>Volume</th>
            <th>Jita Sell Price</th>
            <th>C-J6MT Sell Price</th>
            <th>Import Price</th>
            <th>Purchase Location</th>
            <th>Marked Up Price (+${finalTotals.markup_pct}%)</th>
        </tr>
        `;

        for (const item of items) {
        html += `
            <tr>
            <td>${item.name}</td>
            <td>${item.qty.toLocaleString()}</td>
            <td>${item.volume.toLocaleString()}</td>
            <td>${Math.round(item.subtotal_jita).toLocaleString()}</td>
            <td>${Math.round(item.subtotal_gsf).toLocaleString()}</td>
            <td>${Math.round(item.import_cost).toLocaleString()}
            <td>${item.purchase_loc}</td>
            <td>${Math.round(item.marked_up_price).toLocaleString()}</td>
            </tr>
        `;
        }

        html += "</table>";
    }

    resultsDiv.innerHTML = html;
}