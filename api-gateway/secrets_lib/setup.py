from setuptools import setup, find_packages

setup(
    name="secret-store",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.7",
        "cryptography>=42.0.0",
    ],
    entry_points={
        "console_scripts": [
            "secret-store=secret_store.cli:cli",
        ],
    },
) 