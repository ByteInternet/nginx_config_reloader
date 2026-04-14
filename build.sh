#!/usr/bin/env bash
set -e

ARCH="${ARCH:-amd64}"
DIST="${DIST:-bookworm}"
BUILDAREA="${BUILDAREA:-/tmp/nginx-config-reloader-build}"
BUILDPATH="${BUILDAREA}-${DIST}"
BRANCH="master"

if [ "$(git rev-parse --abbrev-ref HEAD)" != $BRANCH ]; then
    echo "You are not on the $BRANCH branch, aborting"
    exit 1
fi;

export VERSION=$(date "+%Y%m%d.%H%M%S")
echo "Updating project to version $VERSION"
git add pyproject.toml uv.lock

echo "Committing version update"
git commit pyproject.toml uv.lock -m "Update project version to $VERSION"

echo "Generating changelog changelog"
gbp dch --debian-tag="%(version)s" --new-version=$VERSION --debian-branch $BRANCH --release --commit


echo "Building package for $DIST"

git checkout $BRANCH
TEMPBRANCH="$BRANCH-build-$DIST-$VERSION"
git checkout -b $TEMPBRANCH

mkdir -p $BUILDPATH
gbp buildpackage --git-pbuilder --git-export-dir=$BUILDPATH --git-dist=$DIST --git-arch=$ARCH \
--git-debian-branch=$TEMPBRANCH --git-ignore-new

git checkout $BRANCH
git branch -D $TEMPBRANCH

echo
echo "*************************************************************"
echo

echo "Creating tag $VERSION"
git tag $VERSION

echo
echo "*************************************************************"
echo "Package built succesfully!"
echo "--> ${BUILDPATH}/nginx-config-reloader_${VERSION}_all.deb"

echo "Now push the commit with the version update and the tag:"
echo "git push; git push --tags"
