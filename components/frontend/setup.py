from setuptools import setup

setup(
    name="music-arena-frontend",
    packages=["ma_frontend"],
    install_requires=[
        "gradio",
        "requests",
        "pandas",
    ],
)
