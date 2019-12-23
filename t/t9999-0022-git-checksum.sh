#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test repository lock by pre-check-hook for ref_transaction_commit'
. ./test-lib.sh

m=refs/heads/master
topic=refs/heads/topic
bare=bare-repo.git
lockfile=agit-repo.lock
checksum=info/checksum

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

test_expect_success "create an empty checksum before commit" '
	git init --bare "$bare" &&
	(
		cd "$bare" &&
		touch $checksum &&
		create_commits_in . A B C D E F &&
		test -s $checksum &&
		git-checksum
	) >actual &&
	cat >expect<<-EOF &&
	0d884033cad368f27361bc1f0e3e15af
	EOF
	test_cmp expect actual
'

test_expect_success "re-create bare repo, no initial checksum, won't create checksum" '
	test -f "$bare/HEAD" &&
	rm -rf "$bare" &&
	git init --bare "$bare" &&
	(
		cd "$bare" &&
		create_commits_in . A B C D E F &&
		test ! -f $checksum &&
		test_must_fail git-checksum
	) >actual 2>&1 &&
	cat >expect<<-EOF &&
	FATAL: checksum file does not exist, please run \`git-checksum --init\` to create one
	EOF
	test_cmp expect actual
'

test_expect_success "git checksum --init" '
	(
		cd "$bare" &&
		git-checksum --init &&
		test -s $checksum &&
		git-checksum
	) >actual &&
	cat >expect<<-EOF &&
	0d884033cad368f27361bc1f0e3e15af
	EOF
	test_cmp expect actual &&
	git -C "$bare" checksum --verify
'

test_expect_success "git pack-ref, won't change checksum" '
	(
		cd "$bare" &&
		git pack-refs --all &&
		git gc -q &&
		git-checksum
	) >actual &&
	cat >expect<<-EOF &&
	0d884033cad368f27361bc1f0e3e15af
	EOF
	test_cmp expect actual &&
	git -C "$bare" checksum --verify
'

test_expect_success "clone to work" '
	git clone --no-local "$bare" work
'

test_expect_success "create new branch" '
	(
		cd work &&
		git checkout -b next &&
		git push -u origin HEAD
	) &&
	git -C "$bare" show-ref >actual &&
	cat >expect<<-EOF &&
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/heads/master
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/heads/next
	EOF
	test_cmp expect actual
'

test_expect_success "verify checksum after new branch" '
	git -C "$bare" checksum >actual &&
	cat >expect<<-EOF &&
	48431b6a56054eaa35b55f2f327b6fca
	EOF
	test_cmp expect actual &&
	git -C "$bare" checksum -V
'

test_expect_success "create other not well-known references" '
	(
		cd work &&
		git push -u origin HEAD:refs/tmp/abc123456 &&
		git push -u origin HEAD:refs/keep-around/577711d99f417fdc46fdbd13c1cc6361ed90283d &&
		git push -u origin HEAD:refs/remotes/origin/pu
	) &&
	git -C "$bare" show-ref >actual &&
	cat >expect<<-EOF &&
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/heads/master
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/heads/next
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/keep-around/577711d99f417fdc46fdbd13c1cc6361ed90283d
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/remotes/origin/pu
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/tmp/abc123456
	EOF
	test_cmp expect actual
'

test_expect_success "checksum not changed for not well-known refs" '
	git -C "$bare" checksum >actual &&
	cat >expect<<-EOF &&
	48431b6a56054eaa35b55f2f327b6fca
	EOF
	test_cmp expect actual &&
	git -C "$bare" checksum -V
'

test_expect_success "remove branch next" '
	(
		cd work &&
		git checkout master &&
		git push origin :refs/heads/next &&
		git push origin :refs/tmp/abc123456
	) &&
	git -C "$bare" show-ref >actual &&
	cat >expect<<-EOF &&
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/heads/master
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/keep-around/577711d99f417fdc46fdbd13c1cc6361ed90283d
	1f5ec13705f771d780a15c39a83856a81da128a6 refs/remotes/origin/pu
	EOF
	test_cmp expect actual

'

test_expect_success "verify checksum after remove branch" '
	cat >expect<<-EOF &&
	0d884033cad368f27361bc1f0e3e15af
	EOF
	git -C "$bare" checksum >actual &&
	test_cmp expect actual &&
	git -C "$bare" checksum -V
'

test_expect_success "remove checksum" '
	rm "$bare/$checksum" &&
	test_must_fail \
	git -C "$bare" checksum -V
'
test_expect_success "recreate checksum" '
	test ! -e "$bare/$checksum" &&
	git -C "$bare" checksum --init &&
	test   -e "$bare/$checksum" &&
	git -C "$bare" checksum >actual &&
	cat >expect<<-EOF &&
	0d884033cad368f27361bc1f0e3e15af
	EOF
	test_cmp expect actual &&
	git -C "$bare" checksum -V
'

test_done
