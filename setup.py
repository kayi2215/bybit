from setuptools import setup, find_packages

setup(
    name="bybit-bot",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'python-dotenv',
        'pandas',
        'pybit-v5',
        'pymongo',
    ],
)
