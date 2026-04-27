const ADMIN_STORAGE_KEY = "justice-themis.frontend.admin-key";
const IFIND_STORAGE_KEY = "justice-themis.frontend.ifind-token";

// DOM Elements
const adminInput = document.getElementById("adminAccessKeyInput");
const ifindInput = document.getElementById("ifindTokenInput");
const refreshBtn = document.getElementById("refreshButton");
const saveIfindBtn = document.getElementById("saveIfindButton");
const statusTerminal = document.getElementById("refreshStatus");

const metricItems = document.getElementById("metricItems");
const metricOfficial = document.getElementById("metricOfficial");
const metricEditorial = document.getElementById("metricEditorial");

const itemsList = document.getElementById("itemsList");
const handoffPrompt = document.getElementById("handoffPrompt");
const handoffJson = document.getElementById("handoffJson");

// Initialize from local storage
adminInput.value = localStorage.getItem(ADMIN_STORAGE_KEY) || "";
ifindInput.value = localStorage.getItem(IFIND_STORAGE_KEY) || "";

adminInput.addEventListener("input", (e) => {
  localStorage.setItem(ADMIN_STORAGE_KEY, e.target.value.trim());
});
ifindInput.addEventListener("input", (e) => {
  localStorage.setItem(IFIND_STORAGE_KEY, e.target.value.trim());
});

// Logging utility
function logStatus(message, isError = false) {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  const color = isError ? "var(--accent-alert)" : "var(--accent-green)";
  statusTerminal.innerHTML = `<span style="color:${color}">[${time}] ${message}</span><br/>` + statusTerminal.innerHTML;
}

// Fetch headers
function getHeaders() {
  const headers = { "Content-Type": "application/json" };
  const adminKey = localStorage.getItem(ADMIN_STORAGE_KEY);
  if (adminKey) {
    headers["X-Admin-Access-Key"] = adminKey;
  }
  return headers;
}

// Format numbers
function pad(num) {
  return String(num).padStart(2, '0');
}

// API Calls
async function fetchDashboard() {
  try {
    const res = await fetch("/api/v1/dashboard");
    if (!res.ok) throw new Error("Failed to fetch dashboard");
    const data = await res.json();

    if (data.hero) {
      metricItems.textContent = pad(data.hero.total_items || 0);
      metricOfficial.textContent = pad(data.hero.official_count || 0);
      metricEditorial.textContent = pad(data.hero.ready_count || 0);
    }
  } catch (err) {
    logStatus("ERR: Dashboard sync failed", true);
  }
}

async function fetchItems() {
  try {
    const res = await fetch("/items?limit=20");
    if (!res.ok) throw new Error("Failed to fetch items");
    const data = await res.json();

    itemsList.innerHTML = "";
    (data.items || []).forEach(item => {
      const el = document.createElement("div");
      el.className = "news-item";
      el.innerHTML = `
        <div class="news-meta">
          <span>SRC: ${item.source_id || "UNKNOWN"}</span>
          <span>TIER: ${item.coverage_tier || "N/A"}</span>
        </div>
        <div class="news-title">${item.title || "No Title"}</div>
        <div class="news-summary">${item.summary ? item.summary.substring(0, 100) + '...' : ''}</div>
      `;
      itemsList.appendChild(el);
    });
  } catch (err) {
    logStatus("ERR: Items sync failed", true);
  }
}

async function fetchHandoff() {
  try {
    const res = await fetch("/api/v1/analysis/daily/prompt");
    if (res.ok) {
      const data = await res.json();
      handoffPrompt.textContent = data.compiled_prompt || "Prompt payload empty.";
      handoffJson.textContent = JSON.stringify(data, null, 2);
    } else {
      handoffPrompt.textContent = "Awaiting generation or no data for today.";
      handoffJson.textContent = "{}";
    }
  } catch (err) {
    logStatus("ERR: Handoff sync failed", true);
  }
}

// Actions
refreshBtn.addEventListener("click", async () => {
  logStatus("INITIATING SOURCE REFRESH...");
  try {
    const res = await fetch("/refresh", { method: "POST", headers: getHeaders() });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text);
    }
    logStatus("REFRESH COMPLETE. SYNCING DATA.");
    loadAllData();
  } catch (err) {
    logStatus(`REFRESH FAILED: ${err.message}`, true);
  }
});

saveIfindBtn.addEventListener("click", async () => {
  const token = ifindInput.value.trim();
  logStatus("SAVING IFIND CONFIGURATION...");
  try {
    const res = await fetch("/api/v1/config/ifind", {
      method: "POST",
      headers: getHeaders(),
      body: JSON.stringify({ token })
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text);
    }
    logStatus("IFIND CONFIG SAVED.");
  } catch (err) {
    logStatus(`IFIND SAVE FAILED: ${err.message}`, true);
  }
});

function loadAllData() {
  fetchDashboard();
  fetchItems();
  fetchHandoff();
}

// Initialization
logStatus("SYSTEM INITIALIZED. FETCHING TELEMETRY...");
loadAllData();
