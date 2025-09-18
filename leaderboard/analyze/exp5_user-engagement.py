import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from datetime import datetime

# Add the parent directory to the path to find custom modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Import MODELS_METADATA
from config import BATTLE_LOGS_DIR, MODELS_METADATA
from data_loader import load_all_raw_logs

# Define the output directory for analysis results
OUTPUT_DIR = "outputs/analysis"
# Create a set of known model names for efficient filtering
KNOWN_MODELS = set(MODELS_METADATA.keys())

def generate_user_dist_table(df_logs: pd.DataFrame):
    """
    Generates and prints a table showing the distribution of votes per user.
    """
    print("\n--- 📊 User Vote Distribution Table ---")

    # Count the number of votes for each user
    user_counts = df_logs['user_id'].value_counts().reset_index()
    user_counts.columns = ['user_id', 'num_votes']

    # --- ADDED: Find and display the Power User ---
    if not user_counts.empty:
        # value_counts() sorts descending, so the first row is the power user
        power_user = user_counts.iloc[0]
        power_user_id = power_user['user_id']
        max_votes = power_user['num_votes']
        # Print the last 6 characters of the user hash for identification
        print(f"🏆 Power User identified: User ending in ...{power_user_id[-6:]} submitted {max_votes} votes.")
    # --- END OF ADDED SECTION ---

    # Define the bins for grouping, matching the blog post
    bins = [0, 1, 2, 3, 4, 5, 10, 20, 50]
    labels = ['1', '2', '3', '4', '5', '6-10', '11-20', '21-50']
    
    max_votes = user_counts['num_votes'].max()
    if max_votes > 50:
        upper_bound = (max_votes // 50 + 1) * 50
        extra_bins = list(range(100, upper_bound + 1, 50))
        bins.extend(extra_bins)
        for i in range(len(extra_bins)):
            labels.append(f'{extra_bins[i]-49}-{extra_bins[i]}')

    # Categorize users into the defined bins
    user_counts['vote_bin'] = pd.cut(user_counts['num_votes'], bins=bins, labels=labels, right=True)

    # Count the number of users in each bin
    table_data = user_counts['vote_bin'].value_counts().sort_index().reset_index()
    table_data.columns = ['Number of Votes', 'Number of Users']

    print(table_data.to_string(index=False))

def generate_engagement_plot(df_logs: pd.DataFrame):
    """
    Generates and saves a scatter plot of user engagement vs. length of stay.
    """
    print("\n--- 📈 Generating Engagement vs. Length of Stay Plot ---")

    # Convert Unix timestamps to datetime objects
    df_logs['vote_timestamp'] = pd.to_datetime(df_logs['vote_timestamp'], unit='s')
    
    # Group by user to find the first and last vote time for each
    user_stats = df_logs.groupby('user_id')['vote_timestamp'].agg(['count', 'min', 'max']).reset_index()
    user_stats.rename(columns={'count': 'num_votes', 'min': 'first_vote', 'max': 'last_vote'}, inplace=True)

    # Calculate the time span of activity in hours
    user_stats['activity_span_hours'] = (user_stats['last_vote'] - user_stats['first_vote']).dt.total_seconds() / 3600

    # Filter out users with only one vote, as their time span is always zero
    plot_data = user_stats[user_stats['num_votes'] > 1].copy()

    # Create the scatter plot
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(12, 7))
    sns.scatterplot(
        data=plot_data,
        x='num_votes',
        y='activity_span_hours',
        alpha=0.6,
        s=50
    )
    sns.regplot(
        data=plot_data,
        x='num_votes',
        y='activity_span_hours',
        scatter=False,
        color='red',
        line_kws={'linestyle':'--'}
    )

    plt.title('Voting Engagement vs. Platform Stay Duration', fontsize=16, weight='bold')
    plt.xlabel('Number of Votes per User (Engagement)', fontsize=12)
    plt.ylabel('Time Between First and Last Vote (Hours)', fontsize=12)
    plt.xscale('log') 

    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = os.path.join(OUTPUT_DIR, "exp5_user-engagement.png")
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[INFO] Plot saved to {filename}")


def main():
    """
    Main function to load logs and run the analyses.
    """
    print("--- 🚀 Starting User Engagement Analysis ---")
    
    all_raw_logs = load_all_raw_logs(BATTLE_LOGS_DIR)
    
    parsed_votes = []
    for log in tqdm(all_raw_logs, desc="Parsing user votes"):
        
        # --- ADDED: Filter battles to include only known models ---
        try:
            model_a = log.get('a_metadata', {}).get('system_key', {}).get('system_tag')
            model_b = log.get('b_metadata', {}).get('system_key', {}).get('system_tag')

            if not (model_a and model_b and model_a in KNOWN_MODELS and model_b in KNOWN_MODELS):
                continue # Skip if either model is unknown
        except (AttributeError, KeyError):
            continue # Skip if log structure is malformed
        # --- END OF FILTER ---

        vote_user_obj = log.get('vote_user')
        user_id = vote_user_obj.get('salted_ip') if vote_user_obj else None
        
        vote_obj = log.get('vote')
        vote_time = vote_obj.get('preference_time') if vote_obj else None
        
        if user_id and vote_time:
            parsed_votes.append({
                'user_id': user_id,
                'vote_timestamp': vote_time
            })
            
    if not parsed_votes:
        print("\nNo valid vote data found with user IDs and timestamps. Exiting.")
        return
        
    df_logs = pd.DataFrame(parsed_votes)
    print(f"\nFound {len(df_logs)} valid votes from {df_logs['user_id'].nunique()} unique users.")
    
    generate_user_dist_table(df_logs)
    generate_engagement_plot(df_logs)
    
    print("\n--- ✅ Analysis Complete ---")


if __name__ == "__main__":
    main()