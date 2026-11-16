"""
plot_spending.py
----------------
Plots the rolling sum (default: last 28 days) of every category over a time
interval: spending in panels of 4 lines, sorted by their highest value, and
income in its own panel.

Use it from a notebook or another script:

    from plot_spending import plot_rolling_all

    fig, axes = plot_rolling_all(df)                                  # past year
    fig, axes = plot_rolling_all(df, start="2026-01-01")              # Jan 1 until today
    fig, axes = plot_rolling_all(df, start="2025-06-01", end="2025-12-31")

The table needs the columns "Tag" (real dates, not text), "Betrag" and a
category column ("Category" by default, change it with category_col=...).
"""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

INCOME_COLUMNS = ["Income"]
LINE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # fixed order: 1st, 2nd, 3rd, 4th line


def style_panel(ax):
    """Quiet grid and axes, so the lines stand out."""
    # Always show the 0 line, but don't hide values below 0 (money coming in).
    ax.set_ylim(bottom=min(0, ax.get_ylim()[0]))
    ax.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#b5b4ae")
    ax.tick_params(colors="#52514e", length=0, labelsize=8)
    # One tick per month, labelled "Jan 26", "Feb 26", ... on EVERY panel
    # (sharex=True would otherwise only label the bottom row).
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.tick_params(axis="x", labelbottom=True, labelsize=7)
    # Legend ABOVE the panel (bbox_to_anchor y=1.0 = top edge), 2 columns.
    ax.legend(frameon=False, fontsize=9, ncol=2, loc="lower left",
              bbox_to_anchor=(0, 1.0), handlelength=1.5)


def plot_rolling_all(df, window=28, per_panel=4, start=None, end=None,
                     category_col="Category"):
    """Plot the rolling `window`-day sum per category between start and end.

    start, end: dates like "2026-01-01" (or Timestamps). Defaults:
        end   = last date in the data
        start = one year before end
    """
    # 1) daily table + rolling sum over ALL data. Only afterwards we cut out
    #    the interval, so its first days already have a full window behind them.
    daily = (
        df.groupby([pd.Grouper(key="Tag", freq="D"), category_col])["Betrag"]
          .sum()
          .unstack(fill_value=0)
          .resample("D").sum()
    )
    rolling = daily.rolling(window, min_periods=window).sum()

    # 2) the interval to show. pd.Timestamp() turns "2026-01-01" into a date.
    end = rolling.index.max() if end is None else pd.Timestamp(end)
    start = end - pd.DateOffset(years=1) if start is None else pd.Timestamp(start)
    shown = rolling.loc[start:end]
    if shown.empty:
        raise ValueError(f"No data between {start:%Y-%m-%d} and {end:%Y-%m-%d}.")

    # 3) split: income columns vs. everything else (spending, sign flipped)
    income_cols = [c for c in INCOME_COLUMNS if c in shown.columns]
    income = shown[income_cols]
    spending = -shown.drop(columns=income_cols)

    # 4) sort spending categories by their highest value, biggest first
    order = spending.max().sort_values(ascending=False).index

    # 5) cut the sorted list into groups: [0:4], [4:8], [8:12], ...
    groups = [list(order[i:i + per_panel]) for i in range(0, len(order), per_panel)]

    # 6) one panel per group + one for income
    n_panels = len(groups) + (1 if income_cols else 0)
    ncols = 2
    nrows = -(-n_panels // ncols)            # division rounded UP
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 3.6 * nrows),
                             sharex=True, squeeze=False)
    axes = axes.flatten()

    for ax, group in zip(axes, groups):
        for column, color in zip(group, LINE_COLORS):
            ax.plot(spending.index, spending[column], color=color, linewidth=2, label=column)
        style_panel(ax)

    if income_cols:
        income_ax = axes[len(groups)]
        for column, color in zip(income_cols, LINE_COLORS):
            income_ax.plot(income.index, income[column], color=color, linewidth=2, label=column)
        style_panel(income_ax)

    for ax in axes[n_panels:]:               # hide unused panels
        ax.set_visible(False)

    fig.suptitle(f"€ per category in the last {window} days, "
                 f"{shown.index.min():%d.%m.%Y} – {shown.index.max():%d.%m.%Y} "
                 f"(spending positive, sorted by highest value)",
                 x=0.01, ha="left", fontsize=13, color="#0b0b0b")
    fig.tight_layout()
    return fig, axes
