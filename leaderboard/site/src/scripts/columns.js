import { formatScore } from "./data.js";

export const SCORE_COLUMNS = [
  "gitlab_score",
  "reddit_score",
  "shopping_admin_score",
  "shopping_score",
  "wikipedia_score",
  "map_score"
];

export const SITE_COLUMN_LABELS = {
  gitlab_score: "GitLab",
  reddit_score: "Reddit",
  shopping_admin_score: "Shopping Admin",
  shopping_score: "Shopping",
  wikipedia_score: "Wikipedia",
  map_score: "Map"
};

export function createColumns() {
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
    fixedColumns[4],
    ...siteColumns,
    fixedColumns[3],
    ...detailsColumns
  ];
}
