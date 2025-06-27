from setuptools import setup

setup(
    name="music-arena",
    packages=["music_arena"],
    entry_points={
        "console_scripts": [
            "ma-sys=music_arena.cli.system:main",
            "ma-comp=music_arena.cli.component:main",
            "ma-chat=music_arena.cli.chat:main",
            "ma-deploy=music_arena.cli.deploy:main",
        ],
    },
    install_requires=[
        "PyYAML",
        "numpy",
        "soundfile",
        "resampy",
        "openai",
        "fastapi",
        "uvicorn",
        "nest-asyncio",
    ],
)
