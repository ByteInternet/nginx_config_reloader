#!/usr/bin/env bash
set -e

echo "============================================================"
echo "Hypernode Nginx Config Reloader Development Build"
echo " - Will build package from a temp Git branch"
echo " - Will NOT tag the build"
echo " - Will NOT push anything"
echo "============================================================"

ARCH="amd64"
DIST="xenial"
BUILDAREA="${BUILDAREA:-/tmp/nginx-config-reloader-build}"
BUILDPATH="${BUILDAREA}-${DIST}"

CURRENT_BRANCH=`git rev-parse --abbrev-ref HEAD`
if [ -z "$BRANCH" ]; then
    BRANCH="$CURRENT_BRANCH"
fi

export VERSION=$(date "+%Y%m%d.%H%M%S")

git checkout $BRANCH
TEMPBRANCH="$BRANCH-build-$DIST-$VERSION"
git checkout -b $TEMPBRANCH

echo "Updating setup.py with version $VERSION"
perl -pi -e 's/version="[^"]*",/version=\"$ENV{"VERSION"}\",/g;' setup.py

echo "Adding setup.py to git index"
git add setup.py

echo "Committing setup.py version update"
git commit setup.py -m "Update version in setup.py to $VERSION"

echo "Generating changelog changelog"
gbp dch --debian-tag="%(version)s" --new-version=$VERSION --debian-branch $TEMPBRANCH --release --commit


echo "Building package for $DIST"
mkdir -p $BUILDPATH
gbp buildpackage --git-pbuilder --git-export-dir=$BUILDPATH --git-dist=$DIST --git-arch=$ARCH \
--git-debian-branch=$TEMPBRANCH --git-ignore-new

echo
echo "*************************************************************"
echo "Package built succesfully!"
echo "--> ${BUILDPATH}/nginx-config-reloader_${VERSION}_all.deb"
echo
echo "Checking out original branch ..."
git checkout $BRANCH

if [ -z "${KEEP_TEMPBRANCH}" ]; then
    echo "Removing temp Git branch "$TEMPBRANCH" ... (to avoid this set KEEP_TEMPBRANCH env variable)"
    git branch -D $TEMPBRANCH
    echo ""
    echo "You can clear things up by"
    echo "------------------------------------------------------------"
    echo "rm -rf ${BUILDPATH}"
else
    echo "You can clear things up by"
    echo "------------------------------------------------------------"
    echo "git branch -D ${TEMPBRANCH}"
    echo "rm -rf ${BUILDPATH}"
fi
