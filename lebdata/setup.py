from setuptools import setup, find_packages

setup(
    name="lebdata",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask>=3.0.0",
        "pandas>=2.0.0",
        "geopy>=2.3.0",
    ],
    python_requires=">=3.8",
)
