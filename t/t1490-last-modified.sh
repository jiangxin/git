#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test git update-ref create last-modified timestamp'
. ./test-lib.sh

m=refs/heads/master
topic=refs/heads/topic
bare=bare-repo
last_modified=info/last-modified

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
	export GIT_REFS_TXN_NO_HOOK=0 &&
	create_test_commits "" &&
	mkdir $bare &&
	cd $bare &&
	git init --bare &&
	create_test_commits "bare" &&
	cd -
'

test_expect_success "create $m (has GIT_REFS_TXN_NO_HOOK env)" '
	export GIT_REFS_TXN_NO_HOOK=1 &&
	git update-ref $m $A &&
	test $A = $(cat .git/$m) &&
	test ! -f .git/$last_modified
'

test_expect_success "create $topic (no GIT_REFS_TXN_NO_HOOK env)" '
	unset GIT_REFS_TXN_NO_HOOK &&
	git update-ref $topic $A &&
	test $A = $(cat .git/$topic) &&
	test -f .git/$last_modified &&
	printf "$(stat --printf=%y .git/$last_modified)\n" >last-modified-1
'

test_expect_success "update $topic and different last-modified" '
	git update-ref $topic $B &&
	test $B = $(cat .git/$topic) &&
	printf "$(stat --printf=%y .git/$last_modified)\n" >last-modified-2 &&
	! test_cmp last-modified-1 last-modified-2
'

test_expect_success "update $topic without touch last-modified" '
	GIT_REFS_TXN_NO_HOOK=1 git update-ref $topic $C &&
	test $C = $(cat .git/$topic) &&
	printf "$(stat --printf=%y .git/$last_modified)\n" >last-modified-3 &&
	test_cmp last-modified-2 last-modified-3
'

test_done
