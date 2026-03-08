import { describe, expect, it } from "vitest";

import { createColumns } from "../src/scripts/columns.js";

describe("leaderboard site score columns", () => {
  const columns = createColumns();
  const fields = columns.map((col) => col.field).filter(Boolean);

  it("includes all six required per-site score columns", () => {
    const requiredSiteColumns = [
      "gitlab_score",
      "reddit_score",
      "shopping_admin_score",
      "shopping_score",
      "wikipedia_score",
      "map_score"
    ];

    requiredSiteColumns.forEach((column) => {
      expect(fields).toContain(column);
    });
  });

  it("includes the overall_score column", () => {
    expect(fields).toContain("overall_score");
  });

  it("includes rank and name columns", () => {
    expect(fields).toContain("rank");
    expect(fields).toContain("name");
  });
});
