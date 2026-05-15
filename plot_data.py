"""Pure data-preparation helpers for scatter and ternary plots."""

from __future__ import annotations

import pandas as pd


def prepare_xy_data(df: pd.DataFrame, x_col: str, y_col: str, group_col: str | None = None) -> pd.DataFrame:
    """Return aligned numeric x/y rows, preserving group labels when requested."""
    plot_df = pd.DataFrame({
        "_x": pd.to_numeric(df[x_col], errors="coerce"),
        "_y": pd.to_numeric(df[y_col], errors="coerce"),
    })
    if group_col and group_col in df.columns:
        plot_df["_group"] = df[group_col].astype(str)
    return plot_df.dropna(subset=["_x", "_y"])


def prepare_ternary_data(
    df: pd.DataFrame,
    a_col: str,
    b_col: str,
    c_col: str,
    group_col: str | None = None,
) -> pd.DataFrame:
    """Return aligned positive numeric A/B/C rows for ternary plotting."""
    tri_df = pd.DataFrame({
        "_a": pd.to_numeric(df[a_col], errors="coerce"),
        "_b": pd.to_numeric(df[b_col], errors="coerce"),
        "_c": pd.to_numeric(df[c_col], errors="coerce"),
    }).dropna(subset=["_a", "_b", "_c"])
    if group_col and group_col in df.columns:
        tri_df["_group"] = df.loc[tri_df.index, group_col].astype(str)
    return tri_df[(tri_df["_a"] > 0) & (tri_df["_b"] > 0) & (tri_df["_c"] > 0)]

