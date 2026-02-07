import { TabulatorFull as Tabulator } from "tabulator-tables";
import {
  ManifestLoadError,
  TableLoadError,
  formatScore,
  getManifestUrl,
  loadLeaderboardData
} from "./data.js";

let table;
let datasets;
let tableReadyPromise;
let activeBoard = "full";

const dom = {
  loading: document.getElementById("loading-state"),
  content: document.getElementById("content"),
  blockingError: document.getElementById("blocking-error"),
  blockingErrorText: document.getElementById("blocking-error-text"),
  retryButton: document.getElementById("retry-button"),
  inlineError: document.getElementById("inline-error"),
  searchInput: document.getElementById("search-input"),
  exportCsvButton: document.getElementById("export-csv-button"),
  boardTabs: document.querySelectorAll("[data-board]"),
  totalSubmissions: document.getElementById("kpi-total-submissions"),
  lastSubmission: document.getElementById("kpi-last-submission")
};

const SCORE_COLUMNS = [
  "gitlab_score",
  "reddit_score",
  "shopping_admin_score",
  "shopping_score",
  "wikipedia_score",
  "map_score"
];

const SITE_COLUMN_LABELS = {
  gitlab_score: "GitLab",
  reddit_score: "Reddit",
  shopping_admin_score: "Shopping Admin",
  shopping_score: "Shopping",
  wikipedia_score: "Wikipedia",
  map_score: "Map"
};

function createColumns() {
  const fixedColumns = [
    {
      formatter: "responsiveCollapse",
      headerSort: false,
      width: 44,
      minWidth: 44,
      hozAlign: "center",
      resizable: false
    },
    {
      title: "Rank",
      field: "rank",
      sorter: "number",
      width: 86,
      hozAlign: "center"
    },
    {
      title: "Name",
      field: "name",
      sorter: "string",
      minWidth: 220,
      hozAlign: "left"
    },
    { title: "Timestamp", field: "_submission_timestamp", sorter: "string", width: 220, hozAlign: "center" },
    {
      title: "Overall",
      field: "overall_score",
      sorter: "number",
      width: 118,
      hozAlign: "center",
      formatter: (cell) => formatScore(cell.getValue())
    }
  ];

  const siteColumns = SCORE_COLUMNS.map((field) => ({
    title: SITE_COLUMN_LABELS[field],
    field,
    sorter: "number",
    width: 132,
    hozAlign: "center",
    formatter: (cell) => formatScore(cell.getValue()),
    responsive: 0
  }));
  const detailsColumns = [
    {
      title: "Submission ID",
      field: "submission_id",
      sorter: "string",
      width: 420,
      minWidth: 420,
      responsive: 100
    },
    {
      title: "Evaluator",
      field: "webarena_verified_version",
      sorter: "string",
      width: 320,
      minWidth: 320,
      responsive: 99
    }
  ];

  return [
    fixedColumns[0],
    fixedColumns[1],
    fixedColumns[2],
    ...siteColumns,
    fixedColumns[3],
    ...detailsColumns
  ];
}

function setBlockingError(message) {
  dom.loading.hidden = true;
  dom.content.hidden = true;
  dom.blockingError.hidden = false;
  dom.blockingErrorText.textContent = message;
}

function clearBlockingError() {
  dom.blockingError.hidden = true;
  dom.blockingErrorText.textContent = "";
}

function setInlineError(message) {
  dom.inlineError.hidden = false;
  dom.inlineError.textContent = message;
}

function clearInlineError() {
  dom.inlineError.hidden = true;
  dom.inlineError.textContent = "";
}

function applySearchAndFilter() {
  const searchTerm = dom.searchInput.value.trim().toLowerCase();

  const filters = [];

  if (searchTerm.length > 0) {
    filters.push((rowData) => {
      const searchable = `${rowData.name} ${rowData.submission_id}`.toLowerCase();
      return searchable.includes(searchTerm);
    });
  }

  if (filters.length === 0) {
    table.clearFilter(true);
    return;
  }

  table.setFilter((rowData) => filters.every((predicate) => predicate(rowData)));
}

function getBoardRows(boardName) {
  return datasets?.[boardName]?.rows ?? [];
}

function formatTimestamp(timestamp) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(parsed);
}

function updateKpis() {
  const allRows = [...getBoardRows("full"), ...getBoardRows("hard")];
  const uniqueIds = new Set(allRows.map((row) => row.submission_id));
  dom.totalSubmissions.textContent = String(uniqueIds.size);
}

async function loadBoard(boardName) {
  const rows = getBoardRows(boardName);
  await table.replaceData(rows);
  applyHardTableTheme();
  updateKpis();
  applySearchAndFilter();
}

async function setBoard(boardName) {
  activeBoard = boardName;
  dom.boardTabs.forEach((button) => {
    const isActive = button.dataset.board === boardName;
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });

  await loadBoard(boardName);
}

function exportCurrentViewToCsv() {
  if (!table) {
    return;
  }

  const boardSuffix = activeBoard === "hard" ? "hard" : "full";
  const dateStamp = new Date().toISOString().slice(0, 10);
  const filename = `webarena-verified-${boardSuffix}-${dateStamp}.csv`;

  table.download("csv", filename, { bom: true });
}

function attachInteractions() {
  dom.boardTabs.forEach((button) => {
    button.addEventListener("click", () => {
      void setBoard(button.dataset.board);
    });
  });

  dom.searchInput.addEventListener("input", applySearchAndFilter);
  dom.exportCsvButton?.addEventListener("click", exportCurrentViewToCsv);

  dom.retryButton.addEventListener("click", () => {
    start();
  });
}

function initTable() {
  tableReadyPromise = new Promise((resolve) => {
    let settled = false;
    const markReady = () => {
      if (settled) {
        return;
      }
      settled = true;
      resolve();
    };

    table = new Tabulator("#leaderboard-table", {
      data: [],
      layout: "fitColumns",
      responsiveLayout: "collapse",
      responsiveLayoutCollapseStartOpen: false,
      responsiveLayoutCollapseFormatter(data) {
        const submission = data.find((item) => item.title === "Submission ID")?.value ?? "-";
        const evaluator = data.find((item) => item.title === "Evaluator")?.value ?? "-";
        const wrapper = document.createElement("div");
        wrapper.className = "row-details";

        const items = [
          ["Submission ID", submission],
          ["Evaluator", evaluator]
        ];

        items.forEach(([label, value]) => {
          const row = document.createElement("div");
          const labelEl = document.createElement("strong");
          const separatorEl = document.createElement("span");
          const valueEl = document.createElement("span");
          labelEl.className = "row-detail-key";
          separatorEl.className = "row-detail-separator";
          valueEl.className = "row-detail-value";
          labelEl.textContent = label;
          separatorEl.textContent = ":";
          valueEl.textContent = value;
          row.append(labelEl, separatorEl, valueEl);
          wrapper.append(row);
        });

        return wrapper;
      },
      placeholder: "No leaderboard rows available yet.",
      columns: createColumns(),
      pagination: true,
      paginationSize: 25,
      paginationSizeSelector: [10, 25, 50, 100],
      initialSort: [
        { column: "rank", dir: "asc" }
      ]
    });
    table.on("tableBuilt", () => {
      applyHardTableTheme();
      markReady();
    });

    // Fallback: avoid hanging if tableBuilt is delayed/missed in edge cases.
    setTimeout(() => {
      applyHardTableTheme();
      markReady();
    }, 200);
  });
}

function applyHardTableTheme() {
  const root = document.querySelector("#leaderboard-table.tabulator, #leaderboard-table .tabulator");
  const header = document.querySelector("#leaderboard-table.tabulator .tabulator-header, #leaderboard-table .tabulator .tabulator-header");
  const footer = document.querySelector("#leaderboard-table.tabulator .tabulator-footer, #leaderboard-table .tabulator .tabulator-footer");
  const holder = document.querySelector(
    "#leaderboard-table.tabulator .tabulator-tableholder, #leaderboard-table .tabulator .tabulator-tableholder"
  );

  if (root) {
    root.style.setProperty("background-color", "#ffffff", "important");
    root.style.setProperty("border-color", "#d4dff0", "important");
    root.style.setProperty("color", "#1e334a", "important");
  }

  if (header) {
    header.style.setProperty("background-color", "#f8fbff", "important");
    header.style.setProperty("color", "#2c3f55", "important");
    header.style.setProperty("border-bottom", "1px solid #d4dff0", "important");
  }

  if (footer) {
    footer.style.setProperty("background-color", "#f8fbff", "important");
    footer.style.setProperty("color", "#31506d", "important");
    footer.style.setProperty("border-top", "1px solid #d4dff0", "important");
  }

  if (holder) {
    holder.style.setProperty("background-color", "#ffffff", "important");
  }
}

async function start() {
  clearInlineError();
  clearBlockingError();
  dom.loading.hidden = false;
  dom.content.hidden = true;

  let loadedData;
  try {
    loadedData = await loadLeaderboardData(getManifestUrl());
  } catch (error) {
    if (error instanceof ManifestLoadError) {
      setBlockingError(`${error.message} Use retry after verifying publish artifacts are available.`);
      return;
    }

    if (error instanceof TableLoadError) {
      dom.loading.hidden = true;
      dom.content.hidden = false;
      if (!table) {
        initTable();
        attachInteractions();
      }
      setInlineError(`Malformed leaderboard payload: ${error.message}`);
      table.replaceData([]);
      updateKpis();
      return;
    }

    setBlockingError("Unexpected loader error. Retry after checking publish artifacts.");
    return;
  }

  const fallbackSubmissionTimestamp = formatTimestamp(loadedData.manifest.generated_at_utc);
  const withSubmissionTimestamp = (tableFile) => ({
    ...tableFile,
    rows: tableFile.rows.map((row) => ({
      ...row,
      _submission_timestamp: row.submission_timestamp
        ? formatTimestamp(row.submission_timestamp)
        : row.submission_date
          ? formatTimestamp(row.submission_date)
          : fallbackSubmissionTimestamp
    }))
  });

  datasets = {
    full: withSubmissionTimestamp(loadedData.full),
    hard: withSubmissionTimestamp(loadedData.hard)
  };

  if (!table) {
    initTable();
    attachInteractions();
  }
  await tableReadyPromise;

  dom.lastSubmission.textContent = formatTimestamp(loadedData.manifest.generated_at_utc);

  dom.loading.hidden = true;
  dom.content.hidden = false;

  try {
    await setBoard("full");
  } catch (error) {
    setInlineError(`Malformed leaderboard payload: ${error.message}`);
    table.replaceData([]);
    updateKpis();
  }
}

start();
