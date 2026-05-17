const form = document.getElementById("fit-form");

const progressContainer = document.getElementById("progress-container");
const progressBar = document.getElementById("progress-bar");
const statusText = document.getElementById("status-text");
const resultsDiv = document.getElementById("results");
const totalsDiv = document.getElementById("totals");
const buyRecDiv = document.getElementById("buy-recommendations");

if (form) {
form.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Reset UI
    progressContainer.style.display = "block";
    progressBar.value = 0;
    statusText.textContent = "Starting...";
    resultsDiv.innerHTML = "";
    totalsDiv.innerHTML = "";
    buyRecDiv.innerHTML = "";  // Clear previous recommendations

    const formData = new FormData(form);

    const shippingCostInput = form.querySelector('[name="shipping_cost"]');
    const shippingCost = parseFloat(shippingCostInput.value);
    if (isNaN(shippingCost) || shippingCost < 0) {
        shippingCostInput.value = 1200;
        formData.set("shipping_cost", 1200);
    }

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
        buffer = lines.pop() || "";

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
                renderResults(msg.parsed, msg.totals, msg.buy_lists);
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
                renderResults(msg.parsed, msg.totals, msg.buy_lists);
            }
            else if (msg.type === "error") {
                statusText.textContent = `Error: ${msg.message}`;
                console.error(msg.message);
            }
        }

        if (done) break;
    }
});
} // end if (form)

// --- General Import ---
const generalForm = document.getElementById("general-form");
if (generalForm) {
    const generalProgress = document.getElementById("general-progress-container");
    const generalBar = document.getElementById("general-progress-bar");
    const generalStatus = document.getElementById("general-status-text");
    const generalTotals = document.getElementById("general-totals");
    const generalResults = document.getElementById("general-results");

    generalForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        generalProgress.style.display = "block";
        generalBar.value = 0;
        generalStatus.textContent = "Starting...";
        generalTotals.innerHTML = "";
        generalResults.innerHTML = "";

        const formData = new FormData(generalForm);
        const shippingInput = generalForm.querySelector('[name="shipping_cost"]');
        const shippingVal = parseFloat(shippingInput.value);
        if (isNaN(shippingVal) || shippingVal < 0) {
            shippingInput.value = 1200;
            formData.set("shipping_cost", 1200);
        }

        const response = await fetch("/general/stream", { method: "POST", body: formData });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.trim()) continue;
                const msg = JSON.parse(line);
                if (msg.type === "progress") {
                    generalBar.value = (msg.current / msg.total) * 100;
                    generalStatus.textContent = `Processing ${msg.current} / ${msg.total}: ${msg.item}`;
                } else if (msg.type === "done") {
                    generalBar.value = 100;
                    generalStatus.textContent = "Done!";
                    renderGeneralResults(msg.items, msg.totals);
                } else if (msg.type === "error") {
                    generalStatus.textContent = `Error: ${msg.message}`;
                }
            }

            if (done && buffer.trim()) {
                const msg = JSON.parse(buffer);
                if (msg.type === "done") {
                    generalBar.value = 100;
                    generalStatus.textContent = "Done!";
                    renderGeneralResults(msg.items, msg.totals);
                } else if (msg.type === "error") {
                    generalStatus.textContent = `Error: ${msg.message}`;
                }
            }
            if (done) break;
        }
    });
}

function fmt(n) {
    return Math.round(n).toLocaleString('en-US');
}

function renderGeneralResults(items, totals) {
    const generalTotals = document.getElementById("general-totals");
    const generalResults = document.getElementById("general-results");

    if (totals) {
        generalTotals.innerHTML = `
            <h2>Totals</h2>
            <table>
                <tr><th>Total Volume (m³)</th><td>${fmt(totals.volume)}</td></tr>
                <tr><th>Jita Sell Cost</th><td>${fmt(totals.subtotal_jita)}</td></tr>
                <tr><th>Total Import Cost (Jita + Shipping)</th><td>${fmt(totals.import_cost)}</td></tr>
                <tr><th>C-J6MT Sell Value</th><td>${fmt(totals.subtotal_gsf)}</td></tr>
                <tr><th>Profit</th><td>${fmt(totals.profit)}</td></tr>
            </table>`;
    }

    if (items && items.length > 0) {
        let html = `<h2>Items</h2><table>
            <tr>
                <th>Icon</th><th>Name</th><th>Qty</th><th>Volume (m³)</th>
                <th>Jita Sell Price</th><th>C-J6MT Sell Price</th>
                <th>Import Cost</th><th>Profit</th>
            </tr>`;
        for (const item of items) {
            html += `<tr>
                <td><img src="${item.icon}" alt="${item.name} icon" width="32" height="32"></td>
                <td>${item.name}</td>
                <td>${fmt(item.qty)}</td>
                <td>${fmt(item.volume)}</td>
                <td>${fmt(item.subtotal_jita)}</td>
                <td>${fmt(item.subtotal_gsf)}</td>
                <td>${fmt(item.import_cost)}</td>
                <td>${fmt(item.markup)}</td>
            </tr>`;
        }
        html += "</table>";
        generalResults.innerHTML = html;
    }
}

function renderResults(parsed, totals, buy_lists) {
    console.log("renderResults called with parsed:", parsed);
    console.log("totals:", totals);
    console.log("buy_lists:", buy_lists);

    // Render Totals
    if (totals) {
        totalsDiv.innerHTML = `
            <h2>Totals</h2>
            <table>
                <tr><th>Total Volume</th><td>${totals.volume.toLocaleString()}</td></tr>
                <tr><th>Jita Market Price</th><td>${Math.round(totals.subtotal_jita).toLocaleString()}</td></tr>
                <tr><th>C-J6MT Market Price</th><td>${Math.round(totals.subtotal_gsf).toLocaleString()}</td></tr>
                <tr><th>Minimum Obtainable Price</th><td>${Math.round(totals.min_price).toLocaleString()}</td></tr>
                <tr><th>Marked Up Price (+${totals.markup_pct}%)</th><td>${Math.round(totals.marked_up_price).toLocaleString()}</td></tr>
                <tr><th>Profit (+${totals.markup_pct}%)</th><td>${Math.round(totals.profit).toLocaleString()}</td></tr>
            </table>
        `;
    }

    // Render Parsed Fitting
    let html = "<h2>Parsed Fitting</h2>";
    console.log("Checking to see if parsed exists")
    if (parsed) {
        console.log("parsed does exist")
        for (const [section, items] of Object.entries(parsed)) {
            html += `<h3>${section}</h3><table>`;
            html += `
                <tr>
                    <th>Icon</th>
                    <th>Name</th>
                    <th>Qty</th>
                    <th>Volume</th>
                    <th>Jita Sell Price</th>
                    <th>C-J6MT Sell Price</th>
                    <th>Import Price</th>
                    <th>Purchase Location</th>
                    <th>C-J6MT Markup</th>
                </tr>`;

            for (const item of items) {
                console.log(item)
                html += `
                    <tr>
                        <td><img src="${item.icon}" alt="${item.name} icon" width="32" height="32"></td>
                        <td>${item.name}</td>
                        <td>${item.qty.toLocaleString()}</td>
                        <td>${item.volume.toLocaleString()}</td>
                        <td>${Math.round(item.subtotal_jita).toLocaleString()}</td>
                        <td>${Math.round(item.subtotal_gsf).toLocaleString()}</td>
                        <td>${Math.round(item.import_cost).toLocaleString()}</td>
                        <td>${item.purchase_loc}</td>
                        <td>${Math.round(item.markup).toLocaleString()}</td>
                    </tr>`;
            }
            html += "</table>";
        }
    }
    resultsDiv.innerHTML = html;

    // Render Buy Recommendations with extra debug logs
    if (buy_lists) {
        console.log("Entering buy recommendations render - buy_lists exists");
        let buyHtml = `<h2>Purchase Recommendations</h2>
        <table class="table table-bordered">
        <thead>
        <tr>
        <th>JITA</th>
        </tr>
        </thead>
        <tbody>`;
        const jitaList = buy_lists['JITA'] || [];
        const jitaLen = jitaList.length;
        console.log("jitaLen is", jitaLen)
        for (let i = 0; i < jitaLen; i++) {
            buyHtml += '<tr>';
            // JITA column
            buyHtml += '<td>';
            if (jitaList[i]) {
                buyHtml += `${jitaList[i].name} x${jitaList[i].qty.toLocaleString()}`;
            }
            buyHtml += '</td>';
            buyHtml += '</tr>';
        }
        buyHtml += '</tbody></table>';

        buyHtml += `<table class="table table-bordered">
        <thead>
        <tr>
        <th>C-J6MT</th>
        </tr>
        </thead>
        <tbody>`;

        const cjList = buy_lists['C-J'] || [];
        const cjLen = cjList.length;
        console.log("cjLen is", cjLen)
        for (let i = 0; i < cjLen; i++) {
            buyHtml += '<tr>';
            // C-J column
            buyHtml += '<td>';
            if (cjList[i]) {
                buyHtml += `${cjList[i].name} x${cjList[i].qty.toLocaleString()}`;
            }
            buyHtml += '</td>';
            buyHtml += '</tr>';
        }
        
        buyHtml += '</tbody></table>';

        console.log("buyHTML is", buyHtml);
    
        if (buyRecDiv) {
            buyRecDiv.innerHTML = buyHtml;
            console.log("Set innerHTML successfully. Current innerHTML:", buyRecDiv.innerHTML);
        } else {
            console.error("buyRecDiv not found in the DOM");
        }
    } else {
        console.log("buy_lists is falsy - skipping render");
        if (buyRecDiv) {
            buyRecDiv.innerHTML = '<p>No purchase recommendations available.</p>';
        }
    }
}