import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name='pydeezer_asy',
    version='1.2.1',
    description='Asynchronous version of the `py-deezer` module',
    author='drhspfn',
    author_email="drhspfn@gmail.com",
    packages=setuptools.find_packages(),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/drhspfn/deezer-asy",
    install_requires=[
        "aiofiles",
        "cryptography",
        "mutagen",
        "httpx",
        "yarl",
        "asyncio"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent"
    ],

)
