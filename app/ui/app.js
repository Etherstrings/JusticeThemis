const refreshButton = document.getElementById("refreshButton");
const refreshStatus = document.getElementById("refreshStatus");
const adminAccessKeyInput = document.getElementById("adminAccessKeyInput");
const metricItems = document.getElementById("metricItems");
const metricOfficial = document.getElementById("metricOfficial");
const metricEditorial = document.getElementById("metricEditorial");
const itemsList = document.getElementById("itemsList");
const handoffPrompt = document.getElementById("handoffPrompt");
const handoffGroups = document.getElementById("handoffGroups");
const handoffJson = document.getElementById("handoffJson");
const ADMIN_ACCESS_KEY_STORAGE_KEY = "justice-themis.admin-access-key";
const LEGACY_ADMIN_ACCESS_KEY_STORAGE_KEY = "overnight-news-handoff.admin-access-key";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderItems(items) {
  if (!items.length) {
    itemsList.innerHTML = '<div class="empty-state">No captured items yet. Trigger a refresh to pull official sources.</div>';
    return;
  }

  itemsList.innerHTML = items
    .map((item) => {
      const entityNames = (item.entities || []).map((entity) => entity.name).join(", ");
      const numericFacts = (item.numeric_facts || [])
        .map((fact) => `${fact.metric}: ${fact.value} ${fact.unit}${fact.subject ? ` (${fact.subject})` : ""}`)
        .join(" | ");
      const impactLines = [
        item.impact_summary ? `影响概述: ${item.impact_summary}` : "",
        (item.beneficiary_directions || []).length ? `受益方向: ${(item.beneficiary_directions || []).join("、")}` : "",
        (item.pressured_directions || []).length ? `承压方向: ${(item.pressured_directions || []).join("、")}` : "",
        (item.price_up_signals || []).length ? `可能涨价: ${(item.price_up_signals || []).join("、")}` : "",
        (item.follow_up_checks || []).length ? `待确认: ${(item.follow_up_checks || []).join("；")}` : "",
      ].filter(Boolean);
      return `
        <article class="item-card">
          <div class="item-meta">
            <span class="badge">${escapeHtml(item.source_name)}</span>
            <span class="badge secondary">${escapeHtml(item.coverage_tier || item.organization_type || "source")}</span>
            <span class="badge secondary">${escapeHtml(item.published_at || "time unknown")}</span>
            ${item.published_at_source ? `<span class="badge secondary">${escapeHtml(item.published_at_source)}</span>` : ""}
            ${item.summary_quality ? `<span class="badge secondary">${escapeHtml(item.summary_quality)} summary</span>` : ""}
            ${item.a_share_relevance ? `<span class="badge secondary">${escapeHtml(item.a_share_relevance)} A-share</span>` : ""}
            ${item.analysis_status ? `<span class="badge secondary">${escapeHtml(item.analysis_status)} analysis</span>` : ""}
            ${item.excerpt_source ? `<span class="badge secondary">${escapeHtml(item.excerpt_source)}</span>` : ""}
            ${item.excerpt_char_count ? `<span class="badge secondary">${escapeHtml(item.excerpt_char_count)} chars</span>` : ""}
          </div>
          <h3>${escapeHtml(item.title || "Untitled item")}</h3>
          <p class="item-summary">${escapeHtml(item.summary || "No summary extracted yet.")}</p>
          ${item.a_share_relevance_reason ? `<p class="item-summary">${escapeHtml(item.a_share_relevance_reason)}</p>` : ""}
          ${item.analysis_blockers && item.analysis_blockers.length ? `<p class="item-summary impact-line">${escapeHtml(`分析阻塞: ${item.analysis_blockers.join("、")}`)}</p>` : ""}
          ${impactLines.map((line) => `<p class="item-summary impact-line">${escapeHtml(line)}</p>`).join("")}
          <div class="item-footer">
            <a class="item-link" href="${escapeHtml(item.canonical_url)}" target="_blank" rel="noreferrer">Open source</a>
            ${entityNames ? `<span class="badge secondary">Entities: ${escapeHtml(entityNames)}</span>` : ""}
            ${numericFacts ? `<span class="badge secondary">Facts: ${escapeHtml(numericFacts)}</span>` : ""}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderGroups(groups) {
  if (!groups.length) {
    handoffGroups.innerHTML = '<div class="empty-state">No handoff groups yet.</div>';
    return;
  }

  handoffGroups.innerHTML = groups
    .map(
      (group) => `
        <section class="group-card">
          <h3>${escapeHtml(group.title || group.coverage_tier)}</h3>
          <p class="group-summary">${escapeHtml(group.summary || "")}</p>
          <div class="group-items">
            ${(group.items || [])
              .map(
                (item) => `
                  <span class="group-chip">
                    #${escapeHtml(item.item_id)} ${escapeHtml(item.source_name)}: ${escapeHtml(item.title)}
                  </span>
                `
              )
              .join("")}
          </div>
        </section>
      `
    )
    .join("");
}

function updateMetrics(itemsPayload, handoffPayload) {
  metricItems.textContent = String(itemsPayload.total || 0);
  metricOfficial.textContent = String(handoffPayload.official_item_count || 0);
  metricEditorial.textContent = String(handoffPayload.editorial_item_count || 0);
}

async function fetchJson(url, options = undefined) {
  const response = await fetch(url, options);
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error("403 Forbidden. Add the admin access key above or enable unsafe admin mode.");
    }
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function readAdminAccessKey() {
  return String(adminAccessKeyInput?.value ?? "").trim();
}

function buildAdminHeaders() {
  const accessKey = readAdminAccessKey();
  return accessKey ? { "X-Admin-Access-Key": accessKey } : {};
}

function persistAdminAccessKey() {
  if (!adminAccessKeyInput) {
    return;
  }
  const accessKey = readAdminAccessKey();
  try {
    if (accessKey) {
      window.localStorage.setItem(ADMIN_ACCESS_KEY_STORAGE_KEY, accessKey);
    } else {
      window.localStorage.removeItem(ADMIN_ACCESS_KEY_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore storage failures and keep the current in-memory value.
  }
}

function hydrateAdminAccessKey() {
  if (!adminAccessKeyInput) {
    return;
  }
  try {
    const storedValue =
      window.localStorage.getItem(ADMIN_ACCESS_KEY_STORAGE_KEY) ||
      window.localStorage.getItem(LEGACY_ADMIN_ACCESS_KEY_STORAGE_KEY);
    if (storedValue) {
      adminAccessKeyInput.value = storedValue;
    }
  } catch (_error) {
    // Ignore storage failures and continue with a blank field.
  }
}

async function loadDashboard() {
  const [itemsPayload, handoffPayload] = await Promise.all([
    fetchJson("/items?limit=12"),
    fetchJson("/handoff?limit=12"),
  ]);

  renderItems(itemsPayload.items || []);
  renderGroups(handoffPayload.groups || []);
  updateMetrics(itemsPayload, handoffPayload);
  handoffPrompt.textContent = handoffPayload.prompt_scaffold || "Prompt scaffold unavailable.";
  handoffJson.textContent = JSON.stringify(handoffPayload, null, 2);
  refreshStatus.textContent = `Loaded ${itemsPayload.total || 0} items at ${new Date().toLocaleString()}.`;
}

async function runRefresh() {
  refreshButton.disabled = true;
  refreshStatus.textContent = "Refreshing official and editorial source pages...";
  try {
    persistAdminAccessKey();
    const payload = await fetchJson("/refresh?limit_per_source=2&max_sources=6&recent_limit=12", {
      method: "POST",
      headers: buildAdminHeaders(),
    });
    await loadDashboard();
    refreshStatus.textContent = `Refresh complete. ${payload.collected_items || 0} items stored across ${payload.collected_sources || 0} sources.`;
  } catch (error) {
    refreshStatus.textContent = `Refresh failed: ${error.message}`;
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", () => {
  void runRefresh();
});

adminAccessKeyInput?.addEventListener("change", persistAdminAccessKey);
adminAccessKeyInput?.addEventListener("blur", persistAdminAccessKey);

window.loadDashboard = loadDashboard;

hydrateAdminAccessKey();

void loadDashboard().catch((error) => {
  refreshStatus.textContent = `Initial load failed: ${error.message}`;
  itemsList.innerHTML = '<div class="empty-state">The dashboard could not load the current capture state.</div>';
  handoffGroups.innerHTML = '<div class="empty-state">The handoff package is unavailable.</div>';
  handoffJson.textContent = error.message;
});
