const baseUrl = import.meta.env.BASE_URL || "/";
const normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
const envManifestUrl = import.meta.env.PUBLIC_LEADERBOARD_MANIFEST_URL;

export function resolveManifestUrl({ envManifestUrl, baseUrl }) {
  if (typeof envManifestUrl === "string" && envManifestUrl.trim().length > 0) {
    return envManifestUrl.trim();
  }

  const normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return `${normalizedBaseUrl}data/leaderboard_manifest.json`;
}

const MANIFEST_URL = resolveManifestUrl({ envManifestUrl, baseUrl: normalizedBaseUrl });

export const MANIFEST_FETCH_OPTIONS = Object.freeze({ cache: "no-store" });
export const GENERATION_FETCH_OPTIONS = Object.freeze({ cache: "force-cache" });

const REQUIRED_MANIFEST_FIELDS = [
  "schema_version",
  "generation_id",
  "generated_at_utc",
  "full_file",
  "hard_file",
  "full_sha256",
  "hard_sha256"
];

const REQUIRED_ROW_FIELDS = [
  "rank",
  "submission_id",
  "name",
  "overall_score",
  "shopping_score",
  "reddit_score",
  "gitlab_score",
  "wikipedia_score",
  "map_score",
  "shopping_admin_score",
  "success_count",
  "failure_count",
  "error_count",
  "missing_count",
  "webarena_verified_version",
  "checksum"
];

export class ManifestLoadError extends Error {}
export class TableLoadError extends Error {}

function hasFields(objectValue, fieldNames) {
  return fieldNames.every((fieldName) => Object.hasOwn(objectValue, fieldName));
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isSiteScore(value) {
  return value === -1 || (typeof value === "number" && value >= 0 && value <= 1);
}

function isProbability(value) {
  return typeof value === "number" && value >= 0 && value <= 1;
}

export function formatScore(value) {
  if (value === -1) {
    return "N/A";
  }

  if (typeof value !== "number") {
    return "-";
  }

  return `${(value * 100).toFixed(2)}%`;
}

export function validateManifest(payload) {
  if (!isObject(payload)) {
    throw new Error("Manifest payload must be an object.");
  }

  if (!hasFields(payload, REQUIRED_MANIFEST_FIELDS)) {
    throw new Error("Manifest payload is missing required fields.");
  }

  if (typeof payload.full_file !== "string" || typeof payload.hard_file !== "string") {
    throw new Error("Manifest file fields must be strings.");
  }

  const isSha256 = (value) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
  if (!isSha256(payload.full_sha256) || !isSha256(payload.hard_sha256)) {
    throw new Error("Manifest hash fields must be lowercase 64-char SHA256 hex.");
  }

  return payload;
}

export function validateTableFile(payload, leaderboardType) {
  if (!isObject(payload)) {
    throw new Error(`${leaderboardType} payload must be an object.`);
  }

  if (!Array.isArray(payload.rows)) {
    throw new Error(`${leaderboardType} payload rows must be an array.`);
  }

  const rows = payload.rows.map((row, index) => validateRow(row, index, leaderboardType));

  return {
    ...payload,
    rows
  };
}

function validateRow(row, index, leaderboardType) {
  if (!isObject(row) || !hasFields(row, REQUIRED_ROW_FIELDS)) {
    throw new Error(`Malformed row ${index + 1} in ${leaderboardType} payload.`);
  }

  if (!isProbability(row.overall_score)) {
    throw new Error(`Invalid overall_score in row ${index + 1} (${leaderboardType}).`);
  }

  const scoreFields = [
    "shopping_score",
    "reddit_score",
    "gitlab_score",
    "wikipedia_score",
    "map_score",
    "shopping_admin_score"
  ];

  for (const scoreField of scoreFields) {
    if (!isSiteScore(row[scoreField])) {
      throw new Error(`Invalid ${scoreField} in row ${index + 1} (${leaderboardType}).`);
    }
  }

  return row;
}

async function fetchJson(url, options = undefined) {
  const response = await fetch(url, options);

  if (!response.ok) {
    throw new Error(`Fetch failed for ${url} (${response.status}).`);
  }

  return response.json();
}

function resolveManifestFilePath(manifestUrl, manifestFile) {
  return new URL(manifestFile, new URL(manifestUrl, window.location.origin)).pathname;
}

export async function loadLeaderboardData(manifestUrl = MANIFEST_URL) {
  let manifest;
  try {
    manifest = validateManifest(await fetchJson(manifestUrl, MANIFEST_FETCH_OPTIONS));
  } catch (error) {
    throw new ManifestLoadError(error.message);
  }

  let fullPayload;
  let hardPayload;
  try {
    [fullPayload, hardPayload] = await Promise.all([
      fetchJson(resolveManifestFilePath(manifestUrl, manifest.full_file), GENERATION_FETCH_OPTIONS),
      fetchJson(resolveManifestFilePath(manifestUrl, manifest.hard_file), GENERATION_FETCH_OPTIONS)
    ]);
  } catch (error) {
    throw new TableLoadError(error.message);
  }

  try {
    return {
      manifest,
      full: validateTableFile(fullPayload, "full"),
      hard: validateTableFile(hardPayload, "hard")
    };
  } catch (error) {
    throw new TableLoadError(error.message);
  }
}

export function getManifestUrl() {
  return MANIFEST_URL;
}
