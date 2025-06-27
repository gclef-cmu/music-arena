from setuptools import setup

setup(
    name="music-arena-gateway",
    packages=["ma_gateway"],
    install_requires=[
        "fastapi",
        "uvicorn",
        "numpy",
        "soundfile",
        "requests",
        "google-cloud-storage",
        "aiohttp",
    ],
)
