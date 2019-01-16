#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test git update-ref create last-modified timestamp'
. ./test-lib.sh

m=refs/heads/master
topic=refs/heads/topic
bare=a/b/c/bare-repo
lockfile=agit-repo.lock

create_test_commits ()
{
	prfx="$1"
	for name in A B C D E F
	do
		test_tick &&
		T=$(git write-tree) &&
		sha1=$(echo $name | git commit-tree $T) &&
		eval $prfx$name=$sha1
	done
}

test_expect_success setup '
	mkdir -p $bare &&
	cd $bare &&
	git init --bare &&
	create_test_commits "" &&
	cd -
'

cat >expected <<EOF
fatal: update_ref failed for ref 'refs/heads/master': cannot write to repository, locked by file 'agit-repo.lock'.

lock for maintainance.

EOF

test_expect_success "create $m (locked)" '
	cd "$TRASH_DIRECTORY/$bare" &&
	printf "lock for maintainance.\n" >$lockfile &&
	test_must_fail git update-ref $m $A >actual 2>&1 &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

test_expect_success "create $m (bypass locked with environment)" '
	cd "$TRASH_DIRECTORY/$bare" &&
	test -f $lockfile &&
	GIT_REFS_TXN_NO_HOOK=1 git update-ref $m $A
'

test_expect_success "gc pack-refs and git gc works with lockfile" '
	cd "$TRASH_DIRECTORY/$bare" &&
	test -f $lockfile &&
	git pack-refs &&
	git gc -q
'


test_expect_success "update $m (locked)" '
	cd "$TRASH_DIRECTORY/$bare" &&
	test -f $lockfile &&
	test_must_fail git update-ref $m $B >actual 2>&1 &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/expected" <<EOF
fatal: update_ref failed for ref 'refs/heads/master': cannot write to repository, locked by file 'agit-repo.lock'.

lock (root) for maintainance.

EOF

test_expect_success "update $m (root locked)" '
	cd "$TRASH_DIRECTORY/$bare" &&
	rm -f $lockfile &&
	printf "lock (root) for maintainance.\n" >"$TRASH_DIRECTORY/$lockfile" &&
	test_must_fail git update-ref $m $B >actual 2>&1 &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

test_done
