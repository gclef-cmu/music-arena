# Music Arena Leaderboard

The leaderboard is computed transparently from the public [Music Arena Dataset](https://huggingface.co/datasets/music-arena/music-arena-dataset) on HuggingFace.

## Scoring Methodology

- **Arena Score**: [Bradley-Terry model](https://en.wikipedia.org/wiki/Bradley%E2%80%93Terry_model) via L2-regularized logistic regression. Ties are split as half-win / half-loss for each side. Votes with `BOTH_BAD` preference are excluded.
- **95% CI**: Bootstrap resampling (1,000 iterations)
- **Generation Speed (RTF)**: Median Real-Time Factor (audio duration / generation time), normalized to A6000 GPU for open-weights models.
- **Threshold**: Only models with 30+ votes are shown.

For the full scoring implementation, see [`ma_leaderboard/scoring.py`](ma_leaderboard/scoring.py).

## Reproduce the Leaderboard

No credentials required — uses only public HuggingFace data. Runs inside Docker like the other Music Arena components:

```bash
# Generate leaderboard from the public HuggingFace dataset
ma-comp leaderboard leaderboard --output-dir results

# View the generated files
ls results/leaderboards/   # TSV tables
ls results/plots/          # PNG scatter plots
```
