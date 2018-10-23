#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test git update-ref create last-modified timestamp'
. ./test-lib.sh

m=refs/heads/master
topic=refs/heads/topic
bare=bare-repo.git
last_modified=info/last-modified

if test $(uname -s) = "Darwin"; then
	STAT_PROGRAM=gstat
else
	STAT_PROGRAM=stat
fi

create_commits_in () {
	repo="$1" &&
	if ! parent=$(git -C "$repo" rev-parse HEAD^{} 2>/dev/null)
	then
		parent=
	fi &&
	T=$(git -C "$repo" write-tree) &&
	shift &&
	while test $# -gt 0
	do
		name=$1 &&
		test_tick &&
		if test -z "$parent"
		then
			oid=$(echo $name | git -C "$repo" commit-tree $T)
		else
			oid=$(echo $name | git -C "$repo" commit-tree -p $parent $T)
		fi &&
		eval $name=$oid &&
		parent=$oid &&
		shift ||
		return 1
	done &&
	env GIT_REFS_TXN_NO_HOOK=1 git -C "$repo" update-ref $m $oid
}

test_expect_success setup '
	mkdir -p $(dirname "$bare") &&
	git init --bare "$bare" &&
	create_commits_in "$bare" A B C D E F &&
	(
		cd "$bare" &&
		test -f HEAD &&
		test -d info &&
		test ! -f $last_modified
	)
'

test_expect_success "create $m (bypass hook)" '
	(
		cd "$bare" &&
		env GIT_REFS_TXN_NO_HOOK=1 git update-ref $m $A &&
		test ! -f $last_modified
	)
'

test_expect_success "change master to the same commit, won't trigger hook" '
	(
		cd "$bare" &&
		git update-ref $m $A &&
		test ! -f $last_modified
	)
'

test_expect_success "remove no-exist branch, won't trigger hook" '
	(
		cd "$bare" &&
		git update-ref -d refs/heads/non-exist &&
		test ! -f $last_modified
	)
'

test_expect_success "create $topic (run hook)" '
	(
		cd "$bare" &&
		git update-ref $topic $A &&
		test -f $last_modified &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >expect
'

test_expect_success "new ref refs/tmp/* won't change last-modified" '
	(
		cd "$bare" &&
		git update-ref refs/tmp/a $A &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	test_cmp expect actual
'

test_expect_success "new ref refs/keep-around/* won't change last-modified" '
	(
		cd "$bare" &&
		git update-ref refs/keep-around/abcdef0123456789/abcdef0123456789 $B &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	test_cmp expect actual
'

test_expect_success "new ref refs/tags/ will change last-modified" '
	(
		cd "$bare" &&
		git tag -m v1.0.0 v1.0.0 $A &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	! test_cmp expect actual &&
	mv actual expect
'

test_expect_success "new ref refs/merge-requests/ will change last-modified" '
	(
		cd "$bare" &&
		git update-ref refs/merge-requests/123/head $A &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	! test_cmp expect actual &&
	mv actual expect
'

test_expect_success "new ref refs/pull/* will change last-modified" '
	(
		cd "$bare" &&
		git update-ref refs/pull/12/123 $A &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	! test_cmp expect actual &&
	mv actual expect
'

test_expect_success "update $topic and different last-modified" '
	(
		cd "$bare" &&
		git update-ref $topic $B &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	! test_cmp expect actual &&
	mv actual expect
'

test_expect_success "set env, won't update last-modified" '
	(
		cd "$bare" &&
		env GIT_REFS_TXN_NO_HOOK=1 git update-ref $topic $C &&
		printf "$(${STAT_PROGRAM} --printf=%y $last_modified)\n"
	) >actual &&
	test_cmp expect actual
'

test_done
