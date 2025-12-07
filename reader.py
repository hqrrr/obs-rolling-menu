from pathlib import Path
import pandas as pd


def read_data():
    """
    Load the main Excel data file (`data/data.xlsx`) and return both the
    DataFrame and the list of column names.

    Behavior:
    - Resolves the path relative to this module's directory.
    - Raises FileNotFoundError if the file does not exist.
    - Reads the first sheet of the Excel workbook using pandas.
    - Ensures that the file contains at least one column.

    Returns:
        df (pd.DataFrame): The loaded dataset.
        columns (list[str]): List of column headers in the file.

    Raises:
        FileNotFoundError: If data.xlsx cannot be found.
        ValueError: If the Excel file contains no columns.
    """
    base_dir = Path(__file__).resolve().parent
    data_file = base_dir / "data" / "data.xlsx"

    # Verify that the Excel file exists before loading
    if not data_file.exists():
        raise FileNotFoundError(f"Excel file not found: {data_file}")

    # Load the Excel file (first sheet by default)
    df = pd.read_excel(data_file)

    # Ensure the file has at least one column
    if df.shape[1] == 0:
        raise ValueError(
            "The Excel file contains no columns. "
            "Please check the contents of data.xlsx."
        )

    columns = list(df.columns)
    return df, columns


def get_grouped_rows(df, display_col, group_col=None):
    """
    Build a structured list of rows for display in the overlay.

    Output Format:
        [
            {"type": "group", "label": "Group Name"},
            {"type": "item",  "text": "Row Value"},
            ...
        ]

    Behavior:
    - If `group_col` is provided and valid, rows are grouped by `group_col`.
      Each group produces:
          1. A group header row
          2. One item row per value in display_col within that group
    - If no grouping is used, only item rows are returned.
    - Rows with missing values in display_col are excluded.
    - Sorting:
        * With grouping: groups are ordered by `group_col`, and items are
          ordered by display_col (stable sort).
        * Without grouping: original DataFrame order is preserved unless
          customized (sorting is optional and currently disabled).

    Args:
        df (pd.DataFrame): The full dataset.
        display_col (str): Column whose values appear as item text.
        group_col (str | None): Optional column to group by.

    Returns:
        List[dict]: A list of structured row entries ready for JSON response.
    """
    if display_col not in df.columns:
        return []

    # Always include the display column
    cols = [display_col]

    # Determine whether grouping should be applied
    use_group = group_col and group_col in df.columns and group_col != display_col
    if use_group:
        cols.append(group_col)

    # Remove rows where the display value is missing
    sub = df[cols].dropna(subset=[display_col])

    if use_group:
        # Sort groups first, then sort items within each group
        sub = sub.sort_values(by=[group_col, display_col], kind="mergesort")
    else:
        # Ungrouped case: current implementation preserves original DataFrame order
        # Sorting by display_col could be enabled if desired
        pass

    rows = []

    if use_group:
        # Grouped output: emit a group header + item rows per group
        for gval, gdf in sub.groupby(group_col):
            label = str(gval)
            rows.append({
                "type": "group",
                "label": label,
            })
            for v in gdf[display_col].tolist():
                rows.append({
                    "type": "item",
                    "text": str(v),
                })
    else:
        # Ungrouped output: emit item rows only
        for v in sub[display_col].tolist():
            rows.append({
                "type": "item",
                "text": str(v),
            })

    return rows
