from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="onesignal-mcp",
    version="1.0.0",
    author="Weirdbrains",
    author_email="info@weirdbrains.com",
    description="A Model Context Protocol (MCP) server for interacting with the OneSignal API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/weirdbrains/onesignal-mcp",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
    ],
    include_package_data=True,
)
