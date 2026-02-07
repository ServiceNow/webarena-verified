import { describe, expect, it } from "vitest";

import {
  formatScore,
  validateManifest,
  validateTableFile
} from "../src/scripts/data.js";

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
      hard_file: "leaderboard_hard.gen-1.json"
    });

    expect(manifest.generation_id).toBe("gen-1");
  });

  it("rejects malformed manifest payload", () => {
    expect(() => validateManifest({ full_file: "x" })).toThrow("missing required fields");
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
