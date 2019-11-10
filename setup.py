from setuptools import find_packages, setup


def get_long_description():
    return open("README.md", "r", encoding="utf8").read()


setup(
    name="grevillea",
    version="0.0.1",
    packages=find_packages(),
    license="MIT",
    url="https://github.com/erm/grevillea",
    description="Google Cloud Functions support for ASGI",
    long_description=get_long_description(),
    python_requires="~=3.7",
    package_data={"grevillea": ["py.typed"]},
    long_description_content_type="text/markdown",
    author="Jordan Eremieff",
    author_email="jordan@eremieff.com",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
    ],
)
