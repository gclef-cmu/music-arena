# visualizer.py
import matplotlib.pyplot as plt
import seaborn as sns
from adjustText import adjust_text
import pandas as pd
import matplotlib.patches as mpatches

def plot_leaderboard(leaderboard_df: pd.DataFrame, title: str, filename: str):
    """
    Creates a publication-quality plot with legends and label spacing.
    """
    if leaderboard_df.empty:
        print(f"Cannot plot empty leaderboard for '{title}'.")
        return

    plt.style.use('seaborn-v0_8-ticks')
    fig, ax = plt.subplots(figsize=(12, 8))

    color_palette = {
        "Unspecified": "#BBBBBB", # Grey
        "Stock": "#EE8866",       # Orange
        "Open": "#77AADD",        # Blue
        "Commercial": "#EE3377"   # Magenta
    }
    
    markers = {"Open weights": "o", "Proprietary": "^"}

    # Draw the main scatter plot but disable the automatic legend
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
        legend=False  # Disable the default legend to create a custom one
    )

    # --- Axes and Title Formatting ---
    ax.set_xscale('log')
    ax.set_xlabel("Generation Speed (Median RTF, log scale)", fontsize=14, weight='bold')
    ax.set_ylabel("Arena Score", fontsize=14, weight='bold')
    ax.set_title(title, fontsize=18, weight='bold', pad=20)
    ax.tick_params(axis='both', which='major', labelsize=12)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5, color='gray', alpha=0.5)
    sns.despine(ax=ax)

    # --- Text Annotation (with increased spacing) ---
    texts = []
    for _, row in leaderboard_df.iterrows():
        texts.append(ax.text(
            row['Generation Speed (RTF)'],
            row['Arena Score'],
            row['Model'],
            fontsize=11
        ))
    
    # Adjust text to prevent overlap with more space
    adjust_text(
        texts,
        arrowprops=dict(
            arrowstyle='-', 
            color='gray', 
            lw=0.5
        )
    )
    
    # --- Custom Legend Creation ---
    # Create rectangular patch handles for 'training_data'
    data_handles = [mpatches.Patch(color=color_palette[label], label=label) 
                    for label in color_palette if label in leaderboard_df['training_data'].unique()]
    
    # Create marker handles for 'Model Type'
    type_handles = [plt.Line2D([0], [0], marker=marker, color='w', label=label,
                      markerfacecolor='gray', markeredgecolor='black', markersize=10)
                    for label, marker in markers.items() if label in leaderboard_df['access'].unique()]

    # Add the two legends separately with custom spacing and titles
    legend1 = ax.legend(handles=data_handles, title='training_data', 
                        bbox_to_anchor=(1.02, 1), loc='upper left', 
                        labelspacing=1.2, title_fontsize=13, fontsize=11)
    ax.add_artist(legend1) # Add the first legend
    
    ax.legend(handles=type_handles, title='Model Type', 
              bbox_to_anchor=(1.02, 0.65), loc='upper left', 
              labelspacing=1.5, title_fontsize=13, fontsize=11)


    # --- Save and Close ---
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[INFO] Leaderboard plot saved to {filename}")
    plt.close(fig)