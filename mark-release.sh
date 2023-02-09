#!/usr/bin/env bash

read -r -d '' USAGE << EOUSAGE
Mark a release for project, ensure commits in master are in debian changelog.
If there are changes to release, update version and debian changelog,
also can tag and push the release.
If all commits are in changelog, won't change anything.

The last line of output indicates if a release is marked or not.

usage: $0 [options]

options:
    -a          automated mode (commit, tag, push)
    -c          commit the changes for marking the release
    -h          show this help and exit
    -p          git push HEAD and tags
    -t          tag the commit
    -v          verbose output

environment:
    AUTHOR      commit author (name <email>) format
    DEBFULLNAME changelog writer name
    DEBEMAIL    changelog writer email
    MESSAGE     commit message
EOUSAGE

# ==== opts ====
COMMIT=false
PUSH=false
TAG=false
VERBOSE=false

while getopts 'achptv' flag; do
case "$flag" in
    a)
        COMMIT=true
        TAG=true
        PUSH=true
        ;;
    c)
        COMMIT=true
        ;;
    h)
        echo "$USAGE"
        exit
        ;;
    p)
        PUSH=true
        ;;
    t)
        TAG=true
        ;;
    v)
        VERBOSE=true
        ;;
esac
done


set -o errexit

ROOT_DIR=$(realpath $(dirname $0))
CHANGELOG="$ROOT_DIR/debian/changelog"
VERSION=$(date "+%Y%m%d.%H%M%S")
LOG_USER="${SUDO_USER:-$USER}"

# === options from env ====

# committer info
AUTHOR="${AUTHOR:-}"
MESSAGE="${MESSAGE}"
if [[ -z "$MESSAGE" ]]; then
    MESSAGE="[automated] Marking Release $VERSION"
fi

# changelog writer info
export DEBFULLNAME="${DEBFULLNAME:-Hypernode team}"
export DEBEMAIL="${DEBMAIL:-hypernode@byte.nl}"


log() {
    logger --tag 'nginx_config_reloader-mark-release' "[$$ @$LOG_USER] $1"
    if $VERBOSE; then
        echo "$1"
    fi
}

# deb_changelog_updated: returns 0 if there are changes to be released or 1 otherwise
deb_changelog_updated() {
    log "checking if debian changelog needs update"
    # use gbp dch itself to see if there are any changes detected.
    # this way the logic of detecting changes is more consistent with
    # the rest of the system.
    gbp dch --debian-tag="%(version)s" --debian-branch=master
    # find changelog diff to see if there new commits in changelog.
    # commits are usually added like this to the changelog:
    #  [ author ]
    #  * commit message
    # first look for commit messages, if nothing found, then see if there is an empty author section,
    # as a fallback.
    local changed=$(git diff --text --ignore-all-space --unified=0 --no-color $CHANGELOG | grep --line-regexp --perl-regexp '\+\s{2,}\* .+')
    if [[ -z "$changed" ]]; then
        changed=$(git diff --text --ignore-all-space --unified=0 --no-color $CHANGELOG | grep --line-regexp --perl-regexp '\+\\s{2,}\[.+\].*')
    fi
    log "reverting possible changes in debian changelog during update detection"
    git checkout -- $CHANGELOG
    if [[ -n "$changed" ]]; then
        return 0
    fi
    return 1
}

mark_release() {
    log "marking release $VERSION ..."

    local setuppy="$ROOT_DIR/setup.py"
    log "updating setup.py"
    sed -i "s/version=\".*\",/version=\"$VERSION\",/" $setuppy
    git add $setuppy
    log "generating debian changelog"
    gbp dch --debian-tag="%(version)s" --new-version=$VERSION --debian-branch=master
    git add $CHANGELOG
}

commit() {
    log "comitting the release changes"
    if [[ -z "$AUTHOR" ]]; then
        git commit --no-edit --message="$MESSAGE"
    else
        git commit --no-edit --message="$MESSAGE" --author "$AUTHOR"
    fi
}


if ! deb_changelog_updated; then
    log "detected no change, skipping marking release!"
    echo 'no change'
    exit
fi

mark_release

if $COMMIT; then
    commit
    if $TAG; then
        log "creating git tag '$VERSION' ..."
        git tag $VERSION
    fi

    if $PUSH; then
        log "pushing changes to origin ..."
        git push origin HEAD
        if $TAG; then
            git push origin $VERSION
        fi
    fi
else
    log "not committing, skipping tagging and pushing!"
fi

echo "marked release $VERSION"
