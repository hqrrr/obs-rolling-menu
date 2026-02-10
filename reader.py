from pathlib import Path
import pandas as pd
import sys


def _get_app_dir() -> Path:
    """
    Return the directory that contains the running app:
    - In PyInstaller onefile/onedir: directory of the exe
    - In source run: directory of this file (project root side)
    """
    if getattr(sys, "frozen", False):
        # Running as packaged exe
        return Path(sys.executable).resolve().parent
    # Running from source
    return Path(__file__).resolve().parent


def read_data(filename: str = "data.xlsx"):
    """
    Load Excel from the same folder as the exe (preferred).
    """
    app_dir = _get_app_dir()
    data_file = app_dir / filename

    if not data_file.exists():
        raise FileNotFoundError(
            f"Excel file not found next to the application: {data_file}\n"
            f"Please put '{filename}' in the same folder as the exe."
        )

    df = pd.read_excel(data_file)

    if df.shape[1] == 0:
        raise ValueError(
            "The Excel file contains no columns. "
            "Please check the contents of the Excel file."
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
      * Rows where `group_col` is missing (NaN / empty string) are assigned
        to a virtual group labeled "NaN".
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
        for gval, gdf in sub.groupby(group_col, dropna=False):
            # gval can be NaN, empty string, or a normal value
            if pd.isna(gval):
                label = "NaN"
            elif isinstance(gval, str) and not gval.strip():
                label = "NaN"
            else:
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
