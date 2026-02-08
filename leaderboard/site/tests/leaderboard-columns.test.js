import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

describe("leaderboard site score columns", () => {
  it("includes all six required per-site score columns", () => {
    const leaderboardScriptPath = fileURLToPath(new URL("../src/scripts/leaderboard.js", import.meta.url));
    const source = readFileSync(leaderboardScriptPath, "utf8");

    const requiredColumns = [
      "gitlab_score",
      "reddit_score",
      "shopping_admin_score",
      "shopping_score",
      "wikipedia_score",
      "map_score"
    ];

    requiredColumns.forEach((column) => {
      expect(source).toContain(column);
    });
  });
});
