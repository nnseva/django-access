#!/bin/sh

version=$1
shift 1
desc=$*

echo "VERSION:" $version >&2
echo __version__ = \"$version\" >access/__init__.py

git commit -a -m "Fixed version to $version"
git tag $version -a -m "$*"

exit 0
