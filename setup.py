from setuptools import setup, find_namespace_packages

with open("README.md", "r") as fh:
  long_description = fh.read()

with open("VERSION", "r") as fh:
  version = fh.read()

with open("requirements.txt", "r") as fh:
  requirements = fh.readlines()

setup(
  name="bossman",
  version=version,
  author="Anthony Hogg",
  author_email="anthony@hogg.fr",
  description="Automation framework",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/ynohat/bossman",
  entry_points={
    'console_scripts': [
      'bossman = bossman.cli:main',
    ],
  },
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
  ],
  packages=find_namespace_packages(include=['bossman', 'bossman.*']),
  install_requires=requirements,
  python_requires='>=3.5',
  zip_safe=False
)
