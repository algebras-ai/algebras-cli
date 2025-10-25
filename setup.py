from setuptools import setup, find_packages

setup(
    name="algebras-cli",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "colorama>=0.4.4",
        "pyyaml>=6.0",
        "requests>=2.32.3",
        "tqdm>=4.65.0",
        "beautifulsoup4>=4.12.0",
    ],
    entry_points={
        "console_scripts": [
            "algebras=algebras.cli:main",
        ],
    },
    author="Algebras Team",
    author_email="info@example.com",
    description="Powerful AI-driven localization tool for your applications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/algebras-cli",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
) 