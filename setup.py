import os

from setuptools import find_packages, setup


def readme():
    with open("README.md") as fptr:
        return fptr.read()


PACKAGE_NAME = "hahomematic"
HERE = os.path.abspath(os.path.dirname(__file__))
VERSION = "0.0.12"

PACKAGES = find_packages(exclude=["tests", "tests.*", "dist", "build"])

REQUIRES = ["aiohttp>=3.8.0", "voluptuous>=0.12.2"]

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    license="MIT License",
    url="https://github.com/danielperna84/hahomematic",
    download_url="https://github.com/danielperna84/hahomematic/tarball/" + VERSION,
    author="Daniel Perna",
    author_email="danielperna84@gmail.com",
    description="Homematic interface for Home Assistant",
    packages=PACKAGES,
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    python_requires=">=3.8",
    install_requires=REQUIRES,
    keywords=["home", "assistant", "homematic"],
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Topic :: Home Automation",
    ],
)
