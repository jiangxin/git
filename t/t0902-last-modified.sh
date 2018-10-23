#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test git update-ref create last-modified timestamp'

GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main
export GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME

. ./test-lib.sh

m=refs/heads/main
topic=refs/heads/topic
bare=bare-repo.git
last_modified=info/last-modified

create_bare_repo () {
	test "$#" = 1 ||
	BUG "not 1 parameter to test-create-repo"
	repo="$1"
	mkdir -p "$repo"
	(
		cd "$repo" || error "Cannot setup test environment"
		git -c \
			init.defaultBranch="${GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME-master}" \
			init --bare \
			"--template=$GIT_BUILD_DIR/templates/blt/" >&3 2>&4 ||
		error "cannot run git init -- have you built things yet?"
		mv hooks hooks-disabled &&
		git config core.abbrev 7
	) || exit
}

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
	git -C "$repo" update-ref $m $oid
}

restore_repo_last_modified () {
	cp -p "$bare/$last_modified-1" "$bare/$last_modified" &&
	test ! "$bare/$last_modified" -nt "$bare/$last_modified-1" &&
	test ! "$bare/$last_modified" -ot "$bare/$last_modified-1"
}

test_expect_success setup '
	test_when_finished "rm -f $bare/$last_modified" &&
	create_bare_repo "$bare" &&
	create_commits_in "$bare" A B C D E F &&
	test_path_is_file $bare/HEAD &&
	test_path_is_dir  $bare/info &&
	test_path_is_file $bare/$last_modified
'

test_expect_success "update-ref: update timestamp file" '
	test_when_finished "rm -f $bare/$last_modified" &&
	git -C $bare update-ref $m $A &&
	test_path_is_file $bare/$last_modified
'

test_expect_success "change master to the same commit, won't trigger hook" '
	test_when_finished "rm -f $bare/$last_modified" &&
	git -C $bare update-ref $m $A &&
	test_path_is_missing $bare/$last_modified
'

test_expect_success "remove no-exist branch, won't trigger hook" '
	test_when_finished "rm -f $bare/$last_modified" &&
	git -C $bare update-ref -d refs/heads/non-exist &&
	test_path_is_missing $bare/$last_modified
'

test_expect_success "create $topic (run hook)" '
	test_when_finished "rm -f $bare/$last_modified" &&
	git -C "$bare" update-ref $topic $A &&
	test_path_is_file "$bare/$last_modified"
'

test_expect_success "backup last-modified file" '
	touch -t 200504071513.13 "$bare/$last_modified" &&
	cp -p "$bare/$last_modified" "$bare/$last_modified-1" &&
	test ! "$bare/$last_modified" -nt "$bare/$last_modified-1" &&
	test ! "$bare/$last_modified" -ot "$bare/$last_modified-1"
'

test_expect_success "new ref refs/tmp/* won't change last-modified" '
	git -C "$bare" update-ref refs/tmp/a $A &&
	test ! "$bare/$last_modified" -nt "$bare/$last_modified-1" &&
	test ! "$bare/$last_modified" -ot "$bare/$last_modified-1"
'

test_expect_success "new ref refs/keep-around/* won't change last-modified" '
	git -C "$bare" update-ref refs/keep-around/abcdef0123456789/abcdef0123456789 $B &&
	test ! "$bare/$last_modified" -nt "$bare/$last_modified-1" &&
	test ! "$bare/$last_modified" -ot "$bare/$last_modified-1"
'

test_expect_success "new ref refs/tags/ will change last-modified" '
	git -C "$bare" tag -m v1.0.0 v1.0.0 $A &&
	test "$bare/$last_modified" -nt "$bare/$last_modified-1"
'

test_expect_success "restore last-modified" '
	restore_repo_last_modified
'

test_expect_success "new ref refs/merge-requests/ will change last-modified" '
	git -C "$bare" update-ref refs/merge-requests/123/head $A &&
	test "$bare/$last_modified" -nt "$bare/$last_modified-1"
'

test_expect_success "restore last-modified" '
	restore_repo_last_modified
'

test_expect_success "new ref refs/pull/* will change last-modified" '
	git -C "$bare" update-ref refs/pull/12/123 $A &&
	test "$bare/$last_modified" -nt "$bare/$last_modified-1"
'

test_expect_success "restore last-modified" '
	restore_repo_last_modified
'

test_expect_success "update $topic and different last-modified" '
	git -C "$bare" update-ref $topic $B &&
	test "$bare/$last_modified" -nt "$bare/$last_modified-1"
'

test_expect_success "restore last-modified" '
	restore_repo_last_modified
'

test_done
