"""Leaderboard visualization: Arena Score vs Generation Speed (RTF) plots."""

import os

import matplotlib.image as mpimg
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from adjustText import adjust_text
from matplotlib.ticker import FuncFormatter, LogLocator

# Style configuration
STYLE = {
    "title_size": 30,
    "subtitle_size": 24,
    "label_size": 26,
    "tick_size": 22,
    "legend_title": 24,
    "legend_text": 22,
    "annotation": 22,
    "scatter_size": 600,
}


def _add_logo_watermark(ax, logo_path=None, qr_path=None):
    """Add logo and QR code watermarks to the plot axis."""
    if logo_path and os.path.exists(logo_path):
        try:
            img = mpimg.imread(logo_path)
            ax_ins = ax.inset_axes(
                [1.07, 0, 0.20, 0.20], transform=ax.transAxes
            )
            ax_ins.imshow(img, alpha=1.0, resample=True, interpolation="bilinear")
            ax_ins.axis("off")
        except Exception as e:
            print(f"[WARNING] Failed to add logo watermark: {e}")

    if qr_path and os.path.exists(qr_path):
        try:
            qr_img = mpimg.imread(qr_path)
            ax_qr = ax.inset_axes(
                [1.1, -0.1, 0.15, 0.15], transform=ax.transAxes
            )
            ax_qr.imshow(
                qr_img, alpha=1.0, resample=True, interpolation="bilinear"
            )
            ax_qr.axis("off")
        except Exception as e:
            print(f"[WARNING] Failed to add QR code watermark: {e}")


def _plot_on_ax(
    ax,
    leaderboard_df: pd.DataFrame,
    title: str,
    subtitle: str = None,
    ylim: tuple = None,
    xlim: tuple = None,
    logo_path: str = None,
    qr_path: str = None,
):
    """Plot a single leaderboard scatter plot on a given axis."""
    if leaderboard_df.empty:
        ax.text(
            0.5,
            0.5,
            f"No data for '{title}'",
            ha="center",
            va="center",
            fontsize=STYLE["label_size"],
        )
        ax.set_title(title, fontsize=STYLE["title_size"], weight="bold", pad=20)
        return

    color_palette = {
        "Unspecified": "#BBBBBB",
        "Stock": "#EE8866",
        "Open": "#77AADD",
        "Licensed": "#984EA3",
        "Commercial": "#EE3377",
    }
    markers = {"Open weights": "o", "Proprietary": "^"}

    # Scatter plot
    sns.scatterplot(
        data=leaderboard_df,
        x="Generation Speed (RTF)",
        y="Arena Score",
        hue="training_data",
        style="access",
        markers=markers,
        s=STYLE["scatter_size"],
        ax=ax,
        palette=color_palette,
        edgecolor="black",
        linewidth=1.2,
        legend=False,
    )

    # X-axis: log scale with "Nx" format
    ax.set_xscale("log")
    formatter = FuncFormatter(lambda x, pos: f"{x:g}x")
    ax.xaxis.set_major_locator(
        LogLocator(base=10.0, subs=[1.0, 2.0, 3.0, 5.0, 10.0], numticks=15)
    )
    ax.xaxis.set_major_formatter(formatter)

    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    # Labels and title
    ax.set_xlabel(
        "Generation Speed (Median RTF, log scale)",
        fontsize=STYLE["label_size"],
        weight="bold",
        labelpad=20,
    )
    ax.set_ylabel(
        "Arena Score",
        fontsize=STYLE["label_size"],
        weight="bold",
        labelpad=20,
    )
    ax.set_title(
        title, fontsize=STYLE["title_size"], weight="bold", pad=45
    )

    if subtitle:
        ax.text(
            0.5,
            1.02,
            subtitle,
            transform=ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=STYLE["subtitle_size"],
            color="#555555",
            weight="bold",
        )

    # Tick styling
    ax.tick_params(
        axis="both",
        which="major",
        labelsize=STYLE["tick_size"],
        length=10,
        width=2,
    )
    ax.grid(
        True, which="major", linestyle="--", linewidth=1.0, color="gray", alpha=0.5
    )
    sns.despine(ax=ax)

    # Model name annotations
    texts = []
    for _, row in leaderboard_df.iterrows():
        texts.append(
            ax.text(
                row["Generation Speed (RTF)"],
                row["Arena Score"],
                row["Model"],
                fontsize=STYLE["annotation"],
                weight="medium",
            )
        )
    adjust_text(
        texts,
        ax=ax,
        arrowprops=dict(arrowstyle="-", color="gray", lw=1.0),
        force_points=(0.3, 0.6),
    )

    # Legends
    present_training = [
        t
        for t in color_palette.keys()
        if t in leaderboard_df["training_data"].unique()
    ]
    data_handles = [
        mpatches.Patch(color=color_palette[label], label=label)
        for label in present_training
    ]

    present_access = [
        a for a in markers.keys() if a in leaderboard_df["access"].unique()
    ]
    type_handles = [
        plt.Line2D(
            [0],
            [0],
            marker=markers[label],
            color="w",
            label=label,
            markerfacecolor="gray",
            markeredgecolor="black",
            markersize=20,
        )
        for label in present_access
    ]

    first_legend_y = 0.92

    if data_handles:
        legend1 = ax.legend(
            handles=data_handles,
            title="Training Data",
            bbox_to_anchor=(1.02, first_legend_y),
            loc="upper left",
            labelspacing=1.2,
            title_fontsize=STYLE["legend_title"],
            fontsize=STYLE["legend_text"],
            frameon=False,
        )
        legend1.get_title().set_fontweight("bold")
        ax.add_artist(legend1)

    count = len(data_handles) if data_handles else 0
    second_legend_y = first_legend_y - (count * 0.08) - 0.12

    if type_handles:
        legend2 = ax.legend(
            handles=type_handles,
            title="Model Type",
            bbox_to_anchor=(1.02, second_legend_y),
            loc="upper left",
            labelspacing=1.5,
            title_fontsize=STYLE["legend_title"],
            fontsize=STYLE["legend_text"],
            frameon=False,
        )
        legend2.get_title().set_fontweight("bold")

    # Logo watermark
    _add_logo_watermark(ax, logo_path=logo_path, qr_path=qr_path)


def plot_leaderboard(
    inst_df: pd.DataFrame,
    vocal_df: pd.DataFrame,
    inst_filename: str,
    vocal_filename: str,
    combined_filename: str,
    subtitle: str = None,
    logo_path: str = None,
    qr_path: str = None,
):
    """
    Generate and save leaderboard plots with unified X & Y axes.

    Creates three files: instrumental plot, vocal plot, and combined side-by-side.
    """
    # Compute unified Y-axis range
    all_scores = []
    if not inst_df.empty:
        all_scores.append(inst_df["Arena Score"])
    if not vocal_df.empty:
        all_scores.append(vocal_df["Arena Score"])

    if all_scores:
        combined_scores = pd.concat(all_scores)
        y_min, y_max = combined_scores.min(), combined_scores.max()
        padding = (y_max - y_min) * 0.05 if (y_max - y_min) > 0 else 50
        common_ylim = (y_min - padding, y_max + padding)
    else:
        common_ylim = None

    # Compute unified X-axis range (log scale)
    all_speeds = []
    if not inst_df.empty:
        all_speeds.append(inst_df["Generation Speed (RTF)"])
    if not vocal_df.empty:
        all_speeds.append(vocal_df["Generation Speed (RTF)"])

    if all_speeds:
        combined_speeds = pd.concat(all_speeds)
        x_min, x_max = combined_speeds.min(), combined_speeds.max()
        x_min = max(x_min, 1e-2)
        common_xlim = (x_min / 1.5, x_max * 1.5)
    else:
        common_xlim = None

    print(f"[INFO] Common Y-Limit: {common_ylim}")
    print(f"[INFO] Common X-Limit: {common_xlim}")

    plt.style.use("seaborn-v0_8-ticks")

    plot_kwargs = dict(
        ylim=common_ylim,
        xlim=common_xlim,
        logo_path=logo_path,
        qr_path=qr_path,
    )

    # Instrumental plot
    fig1, ax1 = plt.subplots(figsize=(14, 10))
    _plot_on_ax(
        ax1, inst_df, "Instrumental Leaderboard", subtitle, **plot_kwargs
    )
    plt.savefig(inst_filename, dpi=300, bbox_inches="tight")
    plt.close(fig1)

    # Vocal plot
    fig2, ax2 = plt.subplots(figsize=(14, 10))
    _plot_on_ax(
        ax2, vocal_df, "Vocal Leaderboard", subtitle, **plot_kwargs
    )
    plt.savefig(vocal_filename, dpi=300, bbox_inches="tight")
    plt.close(fig2)

    # Combined plot
    fig3, axes = plt.subplots(1, 2, figsize=(28, 11))
    _plot_on_ax(
        axes[0], inst_df, "Instrumental Leaderboard", subtitle, **plot_kwargs
    )
    _plot_on_ax(
        axes[1], vocal_df, "Vocal Leaderboard", subtitle, **plot_kwargs
    )
    plt.tight_layout(rect=[0, 0.0, 0.9, 0.95])
    plt.savefig(combined_filename, dpi=300, bbox_inches="tight")
    plt.close(fig3)

    print(f"[INFO] Saved all plots with unified X & Y axes.")
