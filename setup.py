import setuptools



setuptools.setup(
    name='pydeezer_asy',
    version='1.2.0',
    description='Asynchronous version of the `py-deezer` module',
    author='drhspfn',
    packages=setuptools.find_packages(),
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
