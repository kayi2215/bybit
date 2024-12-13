from setuptools import setup, find_packages

setup(
    name="bybit-bot",
    version="0.1",
    packages=find_packages(include=['src', 'src.*']),
    package_dir={'': '.'},
    install_requires=[
        'python-dotenv',
        'pandas',
        'pybit',
        'pymongo',
        'pytest',
    ],
)
