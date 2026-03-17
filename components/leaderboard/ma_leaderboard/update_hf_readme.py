"""Auto-generate HuggingFace dataset README.md YAML configs from battle_data.

Scans the battle_data/ directory and generates configs for each period found.
No hardcoded month list — new months are auto-detected.
"""

import calendar
import json
from pathlib import Path

NON_PUBLIC_MODELS = {"sao", "sao-small"}


def _parse_folder_name(folder_name):
    """Parse folder like '01-2025JULAUG' -> (config_name, description).

    Examples:
        '01-2025JULAUG' -> ('2025_07-08', 'July and August 2025')
        '02-2025SEP'    -> ('2025_09', 'September 2025')
    """
    parts = folder_name.split("-", 1)
    if len(parts) != 2:
        return folder_name, folder_name

    year_months = parts[1]
    year = year_months[:4]
    months_raw = year_months[4:]

    month_abbr_to_num = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
        "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
        "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }

    # Split into 3-char month abbreviations
    month_abbrs = [months_raw[i:i + 3] for i in range(0, len(months_raw), 3)]
    month_nums = [month_abbr_to_num.get(m) for m in month_abbrs if m in month_abbr_to_num]

    if not month_nums:
        return folder_name, folder_name

    month_names = [calendar.month_name[n] for n in month_nums]

    if len(month_nums) == 1:
        config_name = f"{year}_{month_nums[0]:02d}"
        description = f"{month_names[0]} {year}"
    else:
        config_name = f"{year}_{month_nums[0]:02d}-{month_nums[-1]:02d}"
        description = f"{' and '.join(month_names)} {year}"

    return config_name, description


def _count_period_stats(period_dir):
    """Count battles and audio files for a period."""
    battles = 0
    included_audio = 0
    excluded_audio = 0

    for f in period_dir.glob("*.json"):
        with open(f) as fh:
            d = json.load(fh)
        battles += 1

        for side in ["system_a", "system_b"]:
            model = d.get(side)
            audio_key = "audio_a" if side == "system_a" else "audio_b"
            audio_val = d.get(audio_key)

            if model in NON_PUBLIC_MODELS:
                excluded_audio += 1
            elif audio_val:
                included_audio += 1

    return battles, included_audio, excluded_audio


def update_readme(hf_repo_dir):
    """Regenerate the YAML front matter in the HF dataset README.md."""
    hf_repo_dir = Path(hf_repo_dir)
    readme_path = hf_repo_dir / "README.md"
    battle_dir = hf_repo_dir / "battle_data"

    if not readme_path.exists():
        print(f"README.md not found at {readme_path}")
        return

    content = readme_path.read_text()

    # Split at the closing --- to preserve the body
    parts = content.split("---", 2)
    if len(parts) < 3:
        print("Could not parse README front matter")
        return

    body = parts[2]

    # Scan battle_data/ for existing periods
    periods = sorted(
        [d for d in battle_dir.iterdir() if d.is_dir()],
        key=lambda x: x.name,
    )

    configs_yaml = ""
    for period_dir in periods:
        config_name, description = _parse_folder_name(period_dir.name)
        battles, included, excluded = _count_period_stats(period_dir)

        configs_yaml += f"""
  - config_name: "{config_name}"
    data_files:
      - split: train
        path: "battle_data/{period_dir.name}/*.json"
    description: |
      Data from {description}.
      - Number of Battles: {battles}
      - Audio Files Included in Release: {included}
      - Audio Files Excluded (Not Publicly Released): {excluded}
"""

    new_front_matter = f"""---
license: cc-by-4.0
tags:
  - audio
  - music
  - text-to-music
  - preference-data
  - human-feedback

configs:{configs_yaml}
features:
  audio_a: audio
  audio_b: audio
---"""

    new_content = new_front_matter + body
    readme_path.write_text(new_content)

    print(f"Updated README.md with {len(periods)} configs:")
    for period_dir in periods:
        config_name, _ = _parse_folder_name(period_dir.name)
        battles = len(list(period_dir.glob("*.json")))
        print(f"  {config_name}: {battles} battles")


if __name__ == "__main__":
    import sys
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "music-arena-dataset")
    update_readme(repo_dir)
