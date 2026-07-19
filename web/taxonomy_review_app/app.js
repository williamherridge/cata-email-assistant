const state = {
  runs: [],
  runId: "",
  manifest: null,
  summary: null,
  sample: [],
  filteredSample: [],
  selectedId: null,
  dirty: false,
  catalog: { updated_at: "", categories: [] },
  catalogIndex: { categories: [], subcategories: [] },
  index: { categories: [], subcategories: [] },
  combinedIndex: { categories: [], subcategories: [] },
  draft: {
    approved_category: "",
    approved_subcategory: "",
    review_notes: "",
  },
};

function buildIndexFromSample(sample) {
  const categories = new Map();
  const subcategories = new Map();

  sample.forEach((row) => {
    const category = (row.approved_category || "").trim();
    const subcategory = (row.approved_subcategory || "").trim();

    if (category) {
      categories.set(category, (categories.get(category) || 0) + 1);
    }

    if (category && subcategory) {
      const key = `${category}::${subcategory}`;
      subcategories.set(key, (subcategories.get(key) || 0) + 1);
    }
  });

  return {
    categories: [...categories.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([value, count]) => ({ value, count })),
    subcategories: [...subcategories.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([key, count]) => {
        const [category, value] = key.split("::", 2);
        return { category, value, count };
      }),
  };
}

function mergeIndexes(sampleIndex, catalogIndex) {
  const categories = new Map();
  const subcategories = new Map();

  [...(catalogIndex.categories || []), ...(sampleIndex.categories || [])].forEach((entry) => {
    const existing = categories.get(entry.value);
    if (existing) {
      existing.count = Math.max(existing.count, entry.count || 0);
      existing.source = existing.source === "sample" || entry.source === "sample" ? "sample" : "catalog";
      return;
    }
    categories.set(entry.value, {
      value: entry.value,
      count: entry.count || 0,
      source: entry.source || "sample",
    });
  });

  [...(catalogIndex.subcategories || []), ...(sampleIndex.subcategories || [])].forEach((entry) => {
    const key = `${entry.category}::${entry.value}`;
    const existing = subcategories.get(key);
    if (existing) {
      existing.count = Math.max(existing.count, entry.count || 0);
      existing.source = existing.source === "sample" || entry.source === "sample" ? "sample" : "catalog";
      return;
    }
    subcategories.set(key, {
      category: entry.category,
      value: entry.value,
      count: entry.count || 0,
      source: entry.source || "sample",
    });
  });

  return {
    categories: [...categories.values()].sort((a, b) => b.count - a.count || a.value.localeCompare(b.value)),
    subcategories: [...subcategories.values()].sort(
      (a, b) =>
        b.count - a.count || a.category.localeCompare(b.category) || a.value.localeCompare(b.value),
    ),
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function isReviewed(row) {
  return Boolean((row.approved_category || "").trim());
}

function saveStatus(message) {
  setText("save-status", message);
}

function selectedRow() {
  return state.sample.find((row) => row.id === state.selectedId) || null;
}

function loadDraftFromRow(row) {
  state.draft = {
    approved_category: row ? row.approved_category || "" : "",
    approved_subcategory: row ? row.approved_subcategory || "" : "",
    review_notes: row ? row.review_notes || "" : "",
  };
}

function commitDraftToSelectedRow() {
  const row = selectedRow();
  if (!row) {
    return;
  }

  const nextCategory = (state.draft.approved_category || "").trim();
  const nextSubcategory = (state.draft.approved_subcategory || "").trim();
  const nextNotes = state.draft.review_notes || "";

  const changed =
    (row.approved_category || "") !== nextCategory ||
    (row.approved_subcategory || "") !== nextSubcategory ||
    (row.review_notes || "") !== nextNotes;

  if (!changed) {
    return;
  }

  row.approved_category = nextCategory;
  row.approved_subcategory = nextSubcategory;
  row.review_notes = nextNotes;
  markDirty();
}

function markDirty() {
  state.dirty = true;
  state.index = buildIndexFromSample(state.sample);
  state.combinedIndex = mergeIndexes(state.index, state.catalogIndex);
  saveStatus("Unsaved changes");
}

function renderRunOptions() {
  const select = document.getElementById("run-select");
  select.innerHTML = "";

  state.runs.forEach((run) => {
    const option = document.createElement("option");
    option.value = run.run_id;
    option.textContent = `${run.since} to ${run.through} (${run.sample_size_written})`;
    select.appendChild(option);
  });

  if (state.runs.length) {
    select.value = state.runs[0].run_id;
  }
}

function renderSummary() {
  const container = document.getElementById("summary-stats");
  container.innerHTML = "";

  if (!state.summary || !state.manifest) {
    return;
  }

  const stats = [
    `Records scanned: ${state.summary.record_count || 0}`,
    `Sample rows: ${state.manifest.sample_size_written || 0}`,
    `Inbound: ${(state.summary.direction_counts || {}).inbound || 0}`,
    `Sent: ${(state.summary.direction_counts || {}).sent || 0}`,
    `Other: ${(state.summary.direction_counts || {}).other || 0}`,
  ];

  stats.forEach((line) => {
    const p = document.createElement("p");
    p.textContent = line;
    container.appendChild(p);
  });
}

function renderCategoryCounts() {
  const container = document.getElementById("category-counts");
  const catalogContainer = document.getElementById("catalog-counts");
  const categoryOptions = document.getElementById("category-options");
  const subcategoryOptions = document.getElementById("subcategory-options");
  const seenCategoryOptions = new Set();
  const seenSubcategoryOptions = new Set();
  container.innerHTML = "";
  catalogContainer.innerHTML = "";
  categoryOptions.innerHTML = "";
  subcategoryOptions.innerHTML = "";

  state.index.categories.forEach((entry) => {
    const button = document.createElement("button");
    button.className = "tag-button";
    button.textContent = `${entry.value} (${entry.count})`;
    button.addEventListener("click", () => {
      updateSelectedField("approved_category", entry.value);
      renderDetail();
    });
    container.appendChild(button);

    const option = document.createElement("option");
    if (!seenCategoryOptions.has(entry.value)) {
      option.value = entry.value;
      categoryOptions.appendChild(option);
      seenCategoryOptions.add(entry.value);
    }
  });

  state.combinedIndex.categories.forEach((entry) => {
    if (seenCategoryOptions.has(entry.value)) {
      return;
    }
    const option = document.createElement("option");
    option.value = entry.value;
    categoryOptions.appendChild(option);
    seenCategoryOptions.add(entry.value);
  });

  state.combinedIndex.subcategories.forEach((entry) => {
    if (seenSubcategoryOptions.has(entry.value)) {
      return;
    }
    const option = document.createElement("option");
    option.value = entry.value;
    subcategoryOptions.appendChild(option);
    seenSubcategoryOptions.add(entry.value);
  });

  state.catalogIndex.categories.forEach((entry) => {
    const button = document.createElement("button");
    button.className = "tag-button";
    button.textContent = `${entry.value}${entry.count ? " (" + entry.count + ")" : ""}`;
    button.addEventListener("click", () => {
      updateSelectedField("approved_category", entry.value);
      renderDetail();
    });
    catalogContainer.appendChild(button);
  });

  renderDetailSuggestions();
  renderCatalogMeta();
}

function matchesFilters(row) {
  const statusFilter = document.getElementById("status-filter").value;
  const directionFilter = document.getElementById("direction-filter").value;
  const query = document.getElementById("search-input").value.trim().toLowerCase();

  if (statusFilter === "reviewed" && !isReviewed(row)) {
    return false;
  }
  if (statusFilter === "unreviewed" && isReviewed(row)) {
    return false;
  }
  if (directionFilter !== "all" && row.direction !== directionFilter) {
    return false;
  }
  if (query) {
    const haystack = [
      row.subject,
      row.snippet,
      row.suggested_group,
      row.approved_category,
      row.approved_subcategory,
      row.review_notes,
    ]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(query)) {
      return false;
    }
  }
  return true;
}

function renderMessageList() {
  state.filteredSample = state.sample.filter(matchesFilters);
  const container = document.getElementById("message-items");
  container.innerHTML = "";

  setText("queue-count", `${state.filteredSample.length} visible`);

  state.filteredSample.forEach((row) => {
    const card = document.createElement("div");
    card.className = `message-card ${isReviewed(row) ? "reviewed" : "unreviewed"} ${
      row.id === state.selectedId ? "active" : ""
    }`;
    card.addEventListener("click", () => {
      commitDraftToSelectedRow();
      state.selectedId = row.id;
      loadDraftFromRow(row);
      renderMessageList();
      renderDetail();
    });

    const meta = document.createElement("p");
    meta.className = "small muted";
    meta.textContent = `${row.direction} • ${row.date || "Unknown date"}`;

    const subject = document.createElement("p");
    subject.className = "subject";
    subject.textContent = row.subject || "(No subject)";

    const snippet = document.createElement("p");
    snippet.className = "small";
    snippet.textContent = row.snippet || "";

    const footer = document.createElement("p");
    footer.className = "small muted";
    footer.textContent = row.approved_category
      ? `${row.approved_category}${row.approved_subcategory ? " / " + row.approved_subcategory : ""}`
      : `Suggested: ${row.suggested_group}`;

    card.append(meta, subject, snippet, footer);
    container.appendChild(card);
  });

  if (!state.selectedId && state.filteredSample.length) {
    state.selectedId = state.filteredSample[0].id;
  }

  if (
    state.selectedId &&
    state.filteredSample.length &&
    !state.filteredSample.some((row) => row.id === state.selectedId)
  ) {
    state.selectedId = state.filteredSample[0].id;
  }

  renderDetail();
}

function renderTags(containerId, values) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  values.forEach((value) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = value;
    container.appendChild(span);
  });
}

function renderSuggestionButtons(containerId, values, onClick) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  values.forEach((value) => {
    const button = document.createElement("button");
    button.className = "tag-button";
    button.type = "button";
    button.textContent = value;
    button.addEventListener("click", () => onClick(value));
    container.appendChild(button);
  });
}

function renderDetailSuggestions() {
  const row = selectedRow();
  const categoryValues = state.combinedIndex.categories.map((entry) => entry.value);

  renderSuggestionButtons(
    "approved-category-suggestions",
    categoryValues.slice(0, 16),
    (value) => {
      updateSelectedField("approved_category", value);
      renderDetail();
    },
  );

  if (!row) {
    renderSuggestionButtons("approved-subcategory-suggestions", [], () => {});
    return;
  }

  const activeCategory = (state.draft.approved_category || "").trim();
  const subcategoryValues = state.combinedIndex.subcategories
    .filter((entry) => !activeCategory || entry.category === activeCategory)
    .map((entry) => entry.value)
    .slice(0, 16);

  renderSuggestionButtons(
    "approved-subcategory-suggestions",
    subcategoryValues,
    (value) => {
      updateSelectedField("approved_subcategory", value);
      renderDetail();
    },
  );
}

function renderDetail() {
  const row = selectedRow();
  const empty = document.getElementById("empty-state");
  const content = document.getElementById("detail-content");

  if (!row) {
    empty.classList.remove("hidden");
    content.classList.add("hidden");
    return;
  }

  empty.classList.add("hidden");
  content.classList.remove("hidden");

  setText("detail-date", row.date || "");
  setText("detail-subject", row.subject || "(No subject)");
  setText("detail-from", row.from || "");
  setText("detail-direction", row.direction || "other");
  setText("detail-suggested", row.suggested_group || "unsorted");

  document.getElementById("approved-category").value = state.draft.approved_category || "";
  document.getElementById("approved-subcategory").value = state.draft.approved_subcategory || "";
  document.getElementById("review-notes").value = state.draft.review_notes || "";
  document.getElementById("normalize-scope").value = state.draft.approved_category || "";

  renderTags("detail-keywords", row.keywords || []);
  renderTags("detail-labels", row.labels || []);
  setText("detail-snippet", row.snippet || "");
  renderDetailSuggestions();
}

function renderCatalogMeta() {
  const categoryCount = state.catalog.categories ? state.catalog.categories.length : 0;
  const subcategoryCount = (state.catalog.categories || []).reduce(
    (total, category) => total + (category.subcategories || []).length,
    0,
  );
  const updated = state.catalog.updated_at || "not saved yet";
  setText(
    "catalog-meta",
    `${categoryCount} categories • ${subcategoryCount} subcategories • updated ${updated}`,
  );
}

function updateSelectedField(field, value) {
  state.draft[field] = value;
  commitDraftToSelectedRow();
  renderMessageList();
  renderCategoryCounts();
}

async function loadRuns() {
  const payload = await fetchJson("/api/runs");
  state.runs = payload.runs || [];
  renderRunOptions();
}

async function loadRun(runId) {
  const payload = await fetchJson(`/api/run?id=${encodeURIComponent(runId)}`);
  state.runId = runId;
  state.manifest = payload.manifest;
  state.summary = payload.summary;
  state.sample = payload.sample || [];
  state.catalog = payload.catalog || { updated_at: "", categories: [] };
  state.catalogIndex = payload.catalog_index || { categories: [], subcategories: [] };
  state.index = buildIndexFromSample(state.sample);
  state.combinedIndex = mergeIndexes(state.index, state.catalogIndex);
  state.selectedId = state.sample.length ? state.sample[0].id : null;
  loadDraftFromRow(selectedRow());
  state.dirty = false;

  setText(
    "run-meta",
    `${state.manifest.since} to ${state.manifest.through} • ${state.manifest.sample_size_written} rows • ${state.manifest.run_timestamp}`,
  );
  renderSummary();
  renderCategoryCounts();
  renderMessageList();
  saveStatus("Loaded");
}

async function saveSample() {
  if (!state.runId) {
    return;
  }
  commitDraftToSelectedRow();
  saveStatus("Saving...");
  const payload = await fetchJson("/api/save-sample", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: state.runId, sample: state.sample }),
  });
  state.index = payload.index || state.index;
  state.index = buildIndexFromSample(state.sample);
  state.catalog = payload.catalog || state.catalog;
  state.catalogIndex = payload.catalog_index || state.catalogIndex;
  state.combinedIndex = mergeIndexes(state.index, state.catalogIndex);
  state.dirty = false;
  renderCategoryCounts();
  saveStatus("Saved and catalog updated");
}

async function applyNormalization() {
  const field = document.getElementById("normalize-field").value;
  const oldValue = document.getElementById("normalize-old").value.trim();
  const newValue = document.getElementById("normalize-new").value.trim();
  const categoryScope = document.getElementById("normalize-scope").value.trim();
  const status = document.getElementById("normalize-status");

  if (!oldValue) {
    status.textContent = "Enter a current value to replace.";
    return;
  }

  const payload = await fetchJson("/api/normalize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run_id: state.runId,
      field,
      old_value: oldValue,
      new_value: newValue,
      category_scope: categoryScope,
    }),
  });

  state.sample = payload.sample || state.sample;
  state.index = buildIndexFromSample(state.sample);
  state.combinedIndex = mergeIndexes(state.index, state.catalogIndex);
  status.textContent = `Updated ${payload.updated || 0} rows.`;
  state.dirty = false;
  renderCategoryCounts();
  renderMessageList();
  saveStatus("Saved via normalization");
}

async function promoteReviewedLabels() {
  if (!state.runId) {
    return;
  }

  saveStatus("Promoting labels to catalog...");
  const payload = await fetchJson("/api/promote-sample-labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: state.runId }),
  });

  state.catalog = payload.catalog || state.catalog;
  state.catalogIndex = payload.catalog_index || state.catalogIndex;
  state.combinedIndex = mergeIndexes(state.index, state.catalogIndex);
  renderCategoryCounts();
  saveStatus("Catalog updated");
}

function moveSelection(offset) {
  commitDraftToSelectedRow();
  const index = state.filteredSample.findIndex((row) => row.id === state.selectedId);
  if (index === -1) {
    return;
  }
  const nextIndex = index + offset;
  if (nextIndex < 0 || nextIndex >= state.filteredSample.length) {
    return;
  }
  state.selectedId = state.filteredSample[nextIndex].id;
  loadDraftFromRow(selectedRow());
  renderMessageList();
  renderDetail();
}

function bindEvents() {
  document.getElementById("load-run-btn").addEventListener("click", () => {
    const runId = document.getElementById("run-select").value;
    loadRun(runId).catch((error) => saveStatus(error.message));
  });

  document.getElementById("save-btn").addEventListener("click", () => {
    saveSample().catch((error) => saveStatus(error.message));
  });
  document.getElementById("promote-catalog-btn").addEventListener("click", () => {
    promoteReviewedLabels().catch((error) => saveStatus(error.message));
  });

  document.getElementById("refresh-index-btn").addEventListener("click", renderCategoryCounts);
  document.getElementById("status-filter").addEventListener("change", renderMessageList);
  document.getElementById("direction-filter").addEventListener("change", renderMessageList);
  document.getElementById("search-input").addEventListener("input", renderMessageList);

  document.getElementById("approved-category").addEventListener("input", (event) => {
    state.draft.approved_category = event.target.value;
    renderDetailSuggestions();
  });
  document.getElementById("approved-subcategory").addEventListener("input", (event) => {
    state.draft.approved_subcategory = event.target.value;
  });
  document.getElementById("review-notes").addEventListener("input", (event) => {
    state.draft.review_notes = event.target.value;
  });

  document.getElementById("normalize-btn").addEventListener("click", () => {
    applyNormalization().catch((error) => {
      document.getElementById("normalize-status").textContent = error.message;
    });
  });

  document.getElementById("prev-btn").addEventListener("click", () => moveSelection(-1));
  document.getElementById("next-btn").addEventListener("click", () => moveSelection(1));

  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  });
}

async function init() {
  bindEvents();
  await loadRuns();
  if (state.runs.length) {
    await loadRun(state.runs[0].run_id);
  } else {
    saveStatus("No taxonomy discovery runs found");
  }
}

init().catch((error) => saveStatus(error.message));
