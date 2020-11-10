#!/bin/bash

set -e

if [ -z "$1" ];
then
  echo "usage: $0 major|minor|patch"
  exit 1
fi

bump2version $1
rm -rf dist build *.egg-info
python3 setup.py sdist bdist_wheel
twine upload dist/*