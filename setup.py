#!/usr/bin/env python3
"""
Setup script for Zyntax - NLP-powered Terminal
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="zyntax",
    version="1.0.0",
    author="Rachit",
    author_email="rachit.developer@gmail.com",  # Replace with your actual email
    description="A smart terminal interface that understands natural language commands in English and Hinglish",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/racxhit/Zyntax-NLP-Terminal",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Shells",
        "Topic :: Utilities",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "zyntax=zyntax.cli:main",
        ],
    },
    keywords="nlp terminal cli natural-language command-line artificial-intelligence",
    project_urls={
        "Bug Reports": "https://github.com/racxhit/Zyntax-NLP-Terminal/issues",
        "Source": "https://github.com/racxhit/Zyntax-NLP-Terminal",
        "Documentation": "https://github.com/racxhit/Zyntax-NLP-Terminal#readme",
    },
    include_package_data=True,
    zip_safe=False,
)
