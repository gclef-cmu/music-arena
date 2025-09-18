import matplotlib.pyplot as plt
import seaborn as sns
from adjustText import adjust_text
import pandas as pd
import matplotlib.patches as mpatches

def _plot_on_ax(ax, leaderboard_df: pd.DataFrame, title: str):
    """
    A helper function that draws a single, publication-quality leaderboard plot onto a given Matplotlib axis.
    """
    if leaderboard_df.empty:
        ax.text(0.5, 0.5, f"No data for '{title}'", ha='center', va='center')
        ax.set_title(title, fontsize=18, weight='bold', pad=20)
        return

    color_palette = {
        "Unspecified": "#BBBBBB", # Grey
        "Stock": "#EE8866",       # Orange
        "Open": "#77AADD",        # Blue
        "Commercial": "#EE3377"   # Magenta
    }
    markers = {"Open weights": "o", "Proprietary": "^"}

    sns.scatterplot(
        data=leaderboard_df,
        x="Generation Speed (RTF)",
        y="Arena Score",
        hue="training_data",
        style="access",
        markers=markers,
        s=300,
        ax=ax,
        palette=color_palette,
        edgecolor="black",
        linewidth=0.5,
        legend=False
    )

    ax.set_xscale('log')
    ax.set_xlabel("Generation Speed (Median RTF, log scale)", fontsize=14, weight='bold')
    ax.set_ylabel("Arena Score", fontsize=14, weight='bold')
    ax.set_title(title, fontsize=18, weight='bold', pad=20)
    ax.tick_params(axis='both', which='major', labelsize=12)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray', alpha=0.5)
    sns.despine(ax=ax)

    texts = []
    for _, row in leaderboard_df.iterrows():
        texts.append(ax.text(
            row['Generation Speed (RTF)'],
            row['Arena Score'],
            row['Model'],
            fontsize=11
        ))
    
    adjust_text(
        texts,
        ax=ax, # Specify the axis for adjust_text
        arrowprops=dict(
            arrowstyle='-', 
            color='gray', 
            lw=0.5
        )
    )
    
    data_handles = [mpatches.Patch(color=color_palette[label], label=label) 
                    for label in color_palette if label in leaderboard_df['training_data'].unique()]
    
    type_handles = [plt.Line2D([0], [0], marker=marker, color='w', label=label,
                      markerfacecolor='gray', markeredgecolor='black', markersize=10)
                    for label, marker in markers.items() if label in leaderboard_df['access'].unique()]

    legend1 = ax.legend(handles=data_handles, title='training_data', 
                        bbox_to_anchor=(1.02, 1), loc='upper left', 
                        labelspacing=1.2, title_fontsize=13, fontsize=11)
    ax.add_artist(legend1)
    
    ax.legend(handles=type_handles, title='Model Type', 
              bbox_to_anchor=(1.02, 0.65), loc='upper left', 
              labelspacing=1.5, title_fontsize=13, fontsize=11)

def plot_leaderboard(leaderboard_df: pd.DataFrame, title: str, filename: str):
    """
    Creates a single publication-quality plot by calling the helper function.
    """
    plt.style.use('seaborn-v0_8-ticks')
    fig, ax = plt.subplots(figsize=(12, 8))
    
    _plot_on_ax(ax, leaderboard_df, title)
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Leaderboard plot saved to {filename}")
    plt.close(fig)
    
def plot_combined_leaderboard(inst_df: pd.DataFrame, vocal_df: pd.DataFrame, filename: str):
    """
    Generates and saves a combined plot with instrumental and vocal leaderboards side-by-side.
    """
    plt.style.use('seaborn-v0_8-ticks')
    # Use a wider figure size to accommodate two plots and their legends
    fig, axes = plt.subplots(1, 2, figsize=(24, 9))
    
    # Call the helper function for each subplot
    _plot_on_ax(axes[0], inst_df, "Instrumental Leaderboard")
    _plot_on_ax(axes[1], vocal_df, "Vocal Leaderboard")

    fig.suptitle("Music Arena Leaderboards", fontsize=22, weight='bold')
    # Use tight_layout to adjust spacing between subplots
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Combined plot saved to {filename}")
    plt.close(fig)