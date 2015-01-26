"""The setup and build script for the apkdownloader library."""
import codecs
import os
from setuptools import setup, find_packages

__author__ = 'Igor Nemilentsev'
__author_email__ = 'trezorg@gmail.com'
__version__ = '0.0.1'
tests_require = ['nose']


def read(*names, **kwargs):
    return codecs.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get('encoding', 'utf8')
    ).read()

setup(
    name="apkdownloader",
    version=__version__,
    author=__author__,
    author_email=__author_email__,
    description='Apk downloader with Google Aply API',
    long_description=read('README.md'),
    license='MIT',
    url='https://github.com/trezorg/apkdownloader.git',
    keywords='android, python, apk',
    packages=find_packages(),
    include_package_data=True,
    install_requires=read('requirements.txt').splitlines(),
    test_suite='nose.collector',
    scripts=['apkdownloader/apk.py'],
    tests_require=tests_require,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Communications',
        'Topic :: Internet',
    ],
)
