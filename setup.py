from setuptools import setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name="gamest-retroachievements-plugin",
    description="Add status updates from retroachievements to gamest",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/sopoforic/gamest_retroachievements_plugin',
    author="Tracy Poff",
    author_email="tracy.poff@gmail.com",
    packages=['gamest_plugins.retroachievements'],
    install_requires=['gamest >=3.0, <5.0', 'requests', 'pytz', 'python-dateutil'],
    setup_requires=['setuptools_scm'],
    use_scm_version=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Topic :: Games/Entertainment",
    ],
)
