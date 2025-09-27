"""
Setup script for GM Pricing application.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="gmpricing",
    version="1.0.0",
    author="GM Pricing Team",
    author_email="contact@gmpricing.com",
    description="Medical pricing algorithm application for processing PDFs and calculating costs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yesram72/gmpricing",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gmpricing=main:cli",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)