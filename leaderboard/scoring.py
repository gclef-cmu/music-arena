# scoring.py
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

def compute_arena_score(battles_df: pd.DataFrame, scale=400, base=10, init_rating=1000):
    """Calculates Arena Score similar to Elo using a Bradley-Terry model."""
    models = pd.unique(battles_df[['model_a', 'model_b']].values.ravel('K'))
    model_to_idx = {model: i for i, model in enumerate(models)}
    
    battles_no_ties = battles_df[battles_df['winner'] != 'tie'].copy()
    if battles_no_ties.empty: return {model: init_rating for model in models}

    X, Y = [], []
    for _, row in battles_no_ties.iterrows():
        vec = np.zeros(len(models)); vec[model_to_idx[row['model_a']]] = 1; vec[model_to_idx[row['model_b']]] = -1
        X.append(vec)
        Y.append(1 if row['winner'] == 'model_a' else 0)

    if len(np.unique(Y)) < 2:
        print("Warning: Only one outcome class found. Cannot compute scores accurately.")
        return {model: init_rating for model in models}

    lr = LogisticRegression(fit_intercept=False, penalty=None, tol=1e-8)
    lr.fit(X, Y)
    
    scores = scale * lr.coef_[0] / np.log(base) + init_rating
    
    final_scores = {model: score for model, score in zip(models, scores)}
    for model in models:
        if model not in final_scores: final_scores[model] = init_rating
            
    return final_scores

def calculate_rtf(battles_df: pd.DataFrame, models: list):
    """Calculates the Median Real-Time Factor (RTF) for each model."""
    rtfs = {}
    for model in models:
        rtf_a = (battles_df[battles_df['model_a'] == model]['duration_a'] / battles_df[battles_df['model_a'] == model]['generation_time_a'])
        rtf_b = (battles_df[battles_df['model_b'] == model]['duration_b'] / battles_df[battles_df['model_b'] == model]['generation_time_b'])
        all_rtfs = pd.concat([rtf_a, rtf_b])
        rtfs[model] = all_rtfs.median() if not all_rtfs.empty else np.nan
    return rtfs