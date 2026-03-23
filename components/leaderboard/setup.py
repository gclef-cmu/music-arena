from setuptools import setup

setup(
    name="music-arena-leaderboard",
    packages=["ma_leaderboard"],
    install_requires=[
        "pandas",
        "numpy",
        "scikit-learn",
        "matplotlib",
        "seaborn",
        "adjustText",
        "requests",
        "tqdm",
        "pyarrow",
    ],
    extras_require={
        "gcp": ["google-cloud-storage"],
        "hf-push": ["huggingface_hub"],
    },
    entry_points={
        "console_scripts": [
            "ma-leaderboard=ma_leaderboard.cli:main",
        ],
    },
)
