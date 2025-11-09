from setuptools import setup, find_packages

setup(
    name='queuectl',
    version='0.1.0',
    description='A simple background job queue CLI for internship assignment',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click>=8.0',
    ],
    entry_points={
        'console_scripts': [
            'queuectl=queuectl.cli:cli',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
