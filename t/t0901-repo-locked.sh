#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test repository lock by pre-check-hook for ref_transaction_commit'
. ./test-lib.sh

m=refs/heads/master
topic=refs/heads/topic
bare=a/b/c/bare-repo.git
lockfile=agit-repo.lock

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
	env GIT_REFS_TXN_NO_HOOK=1 \
		git -C "$repo" update-ref $m $oid
}

test_expect_success setup '
	mkdir -p $(dirname "$bare") &&
	git init --bare "$bare" &&
	create_commits_in "$bare" A B C D E F
'

test_expect_success "create repo with lock and fail to update-ref (locked)" '
	(
		cd "$bare" &&
		printf "lock for maintainance." >$lockfile &&
		test_must_fail git update-ref "$m" "$A"
	) >actual 2>&1 &&
	cat >expect <<-EOF &&
	fatal: update_ref failed for ref '"'"'refs/heads/master'"'"': cannot write to repository, locked by file '"'"'agit-repo.lock'"'"'.

	lock for maintainance.
	EOF
	test_cmp expect actual
'

test_expect_success "update master (bypass locked with env)" '
	(
		cd "$bare" &&
		test -f $lockfile &&
		env GIT_REFS_TXN_NO_HOOK=1 git update-ref $m $A &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	102939797ab91a4f201d131418d2c9d919dcdd2c refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "pack-refs works even with lock" '
	(
		cd "$bare" &&
		test -f refs/heads/master &&
		git pack-refs --all &&
		test ! -f refs/heads/master
	)
'

test_expect_success "move lock file to upper dir" '
	mv "$bare/$lockfile" "$lockfile"
'

test_expect_success "cannot create tag (locked)" '
	(
		cd "$bare" &&
		test ! -f $lockfile &&
		test -f "$HOME/$lockfile" &&
		test_must_fail git tag -m v1.0 v1.0 refs/heads/master
	) >actual 2>&1 &&
	cat >expect <<-EOF &&
	fatal: cannot write to repository, locked by file '"'"'agit-repo.lock'"'"'.
	
	lock for maintainance.
	EOF
	test_cmp expect actual
'

test_expect_success "create tag with env, and gc works with lock" '
	(
		cd "$bare" &&
		env GIT_REFS_TXN_NO_HOOK=1 git tag -m v1.0 v1.0 refs/heads/master &&
		test -f refs/tags/v1.0 &&
		git gc -q &&
		test ! -f refs/tags/v1.0
	)
'

test_expect_success "clone and create local branches/tags (set env to bypass)" '
	env GIT_REFS_TXN_NO_HOOK=1 git clone --no-local "$bare" work &&
	create_commits_in work H I J K &&
	(
		cd work &&
		env GIT_REFS_TXN_NO_HOOK=1 git tag -m v1.1 v1.1 $H &&
		env GIT_REFS_TXN_NO_HOOK=1 git tag -m v1.2 v1.2 $I &&
		env GIT_REFS_TXN_NO_HOOK=1 git tag -m v1.3 v1.3 $J &&
		env GIT_REFS_TXN_NO_HOOK=1 git branch dev $K
	)
'

test_expect_success "fail to push one ref" '
	(
		cd work &&
		test_must_fail git push origin v1.1
	) >out 2>&1 &&
	grep -q "remote: lock for maintainance." out
'

test_expect_success "fail to push multiple refs" '
	(
		cd work &&
		test_must_fail git push origin v1.1 v1.2 v1.3 dev
	) &&
	(
		cd "$bare" &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	102939797ab91a4f201d131418d2c9d919dcdd2c refs/heads/master
	5bcd15c7dc073c4b0fef68f89a10ff051cc935a5 refs/tags/v1.0
	EOF
	test_cmp expect actual
'

test_expect_success "no lock, push ok" '
	rm "$lockfile" &&
	(
		cd work &&
		git push origin v1.1 v1.2 v1.3 dev
	) &&
	(
		cd "$bare" &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	50206c8eaea8502922f89743920d674028d36869 refs/heads/dev
	102939797ab91a4f201d131418d2c9d919dcdd2c refs/heads/master
	5bcd15c7dc073c4b0fef68f89a10ff051cc935a5 refs/tags/v1.0
	5abd42d84207715e1bf009dfeed777f6a7bc97cf refs/tags/v1.1
	76303b2db0ccb52e22683df7e438169a725c7afc refs/tags/v1.2
	4c44b8cf5f3c9eb26ebf8e2d513de6ce2ade2050 refs/tags/v1.3
	EOF
	test_cmp expect actual
'

test_done
