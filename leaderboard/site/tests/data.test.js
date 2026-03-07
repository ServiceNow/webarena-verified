import { afterEach, describe, expect, it, vi } from "vitest";

import {
  GENERATION_FETCH_OPTIONS,
  MANIFEST_FETCH_OPTIONS,
  formatScore,
  loadLeaderboardData,
  resolveManifestUrl,
  validateManifest,
  validateTableFile
} from "../src/scripts/data.js";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.window = originalWindow;
  vi.restoreAllMocks();
});

describe("formatScore", () => {
  it("formats sentinel -1 as N/A", () => {
    expect(formatScore(-1)).toBe("N/A");
  });

  it("formats probabilities as percentages", () => {
    expect(formatScore(0.9325)).toBe("93.25%");
  });
});

describe("validateManifest", () => {
  it("accepts valid manifest payload", () => {
    const manifest = validateManifest({
      schema_version: "1.0",
      generation_id: "gen-1",
      generated_at_utc: "2026-02-07T12:00:00Z",
      full_file: "leaderboard_full.gen-1.json",
      hard_file: "leaderboard_hard.gen-1.json",
      full_sha256: "a".repeat(64),
      hard_sha256: "b".repeat(64)
    });

    expect(manifest.generation_id).toBe("gen-1");
  });

  it("rejects malformed manifest payload", () => {
    expect(() => validateManifest({ full_file: "x" })).toThrow("missing required fields");
  });

  it("rejects invalid hash fields", () => {
    expect(() =>
      validateManifest({
        schema_version: "1.0",
        generation_id: "gen-1",
        generated_at_utc: "2026-02-07T12:00:00Z",
        full_file: "leaderboard_full.gen-1.json",
        hard_file: "leaderboard_hard.gen-1.json",
        full_sha256: "A".repeat(64),
        hard_sha256: "b".repeat(63)
      })
    ).toThrow("Manifest hash fields");
  });
});

describe("resolveManifestUrl", () => {
  it("prefers PUBLIC_LEADERBOARD_MANIFEST_URL when provided", () => {
    const manifestUrl = resolveManifestUrl({
      envManifestUrl: "  https://raw.githubusercontent.com/ServiceNow/webarena-verified/leaderboard-submissions/leaderboard_manifest.json  ",
      baseUrl: "/webarena-verified/leaderboard/"
    });

    expect(manifestUrl).toBe("https://raw.githubusercontent.com/ServiceNow/webarena-verified/leaderboard-submissions/leaderboard_manifest.json");
  });

  it("falls back to base-local manifest path", () => {
    const manifestUrl = resolveManifestUrl({
      envManifestUrl: "",
      baseUrl: "/webarena-verified/leaderboard"
    });

    expect(manifestUrl).toBe("/webarena-verified/leaderboard/data/leaderboard_manifest.json");
  });
});

describe("validateTableFile", () => {
  it("accepts empty rows", () => {
    const payload = validateTableFile(
      {
        schema_version: "1.0",
        generation_id: "gen-1",
        generated_at_utc: "2026-02-07T12:00:00Z",
        leaderboard: "full",
        rows: []
      },
      "full"
    );

    expect(payload.rows).toEqual([]);
  });

  it("rejects malformed row payload", () => {
    expect(() =>
      validateTableFile(
        {
          schema_version: "1.0",
          generation_id: "gen-1",
          generated_at_utc: "2026-02-07T12:00:00Z",
          leaderboard: "hard",
          rows: [{ rank: 1 }]
        },
        "hard"
      )
    ).toThrow("Malformed row");
  });

  it("rejects invalid site score values", () => {
    expect(() =>
      validateTableFile(
        {
          schema_version: "1.0",
          generation_id: "gen-1",
          generated_at_utc: "2026-02-07T12:00:00Z",
          leaderboard: "full",
          rows: [
            {
              rank: 1,
              submission_id: "sub-1",
              name: "Team/Model",
              overall_score: 0.9,
              shopping_score: 2,
              reddit_score: 0.8,
              gitlab_score: 0.9,
              wikipedia_score: -1,
              map_score: 0.7,
              shopping_admin_score: 0.6,
              success_count: 10,
              failure_count: 1,
              error_count: 0,
              missing_count: 0,
              webarena_verified_version: "1.0.0",
              checksum: "a".repeat(64)
            }
          ]
        },
        "full"
      )
    ).toThrow("Invalid shopping_score");
  });
});

describe("loadLeaderboardData caching behavior", () => {
  it("uses no-store for manifest and force-cache for generation files", async () => {
    const manifest = {
      schema_version: "1.0",
      generation_id: "gen-1",
      generated_at_utc: "2026-02-07T12:00:00Z",
      full_file: "leaderboard_full.gen-1.json",
      hard_file: "leaderboard_hard.gen-1.json",
      full_sha256: "a".repeat(64),
      hard_sha256: "b".repeat(64)
    };

    const row = {
      rank: 1,
      submission_id: 101,
      name: "Team/Model",
      overall_score: 0.9,
      shopping_score: 0.9,
      reddit_score: 0.9,
      gitlab_score: 0.9,
      wikipedia_score: 0.9,
      map_score: 0.9,
      shopping_admin_score: 0.9,
      success_count: 10,
      failure_count: 0,
      error_count: 0,
      missing_count: 0,
      webarena_verified_version: "1.0.0",
      checksum: "f".repeat(64)
    };

    const fullTable = {
      schema_version: "1.0",
      generation_id: "gen-1",
      generated_at_utc: "2026-02-07T12:00:00Z",
      leaderboard: "full",
      rows: [row]
    };
    const hardTable = {
      ...fullTable,
      leaderboard: "hard"
    };

    const calls = [];
    globalThis.window = { location: { origin: "https://site.example.com" } };
    globalThis.fetch = vi.fn(async (url, options) => {
      calls.push([url, options]);
      if (url === "https://data.example.com/leaderboard_manifest.json") {
        return { ok: true, json: async () => manifest };
      }
      if (url === "/leaderboard_full.gen-1.json") {
        return { ok: true, json: async () => fullTable };
      }
      if (url === "/leaderboard_hard.gen-1.json") {
        return { ok: true, json: async () => hardTable };
      }
      return { ok: false, status: 404, json: async () => ({}) };
    });

    const payload = await loadLeaderboardData("https://data.example.com/leaderboard_manifest.json");

    expect(payload.manifest.generation_id).toBe("gen-1");
    expect(calls).toHaveLength(3);
    expect(calls[0]).toEqual(["https://data.example.com/leaderboard_manifest.json", MANIFEST_FETCH_OPTIONS]);
    expect(calls[1]).toEqual(["/leaderboard_full.gen-1.json", GENERATION_FETCH_OPTIONS]);
    expect(calls[2]).toEqual(["/leaderboard_hard.gen-1.json", GENERATION_FETCH_OPTIONS]);
  });
});
