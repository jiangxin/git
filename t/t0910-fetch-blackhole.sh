#!/bin/sh
#
# Copyright (c) 2019 Jiang Xin
#

test_description='Test git clone/fetch --black-hole'
. ./test-lib.sh

bare=bare-repo.git

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
	git -C "$repo" update-ref refs/heads/master $oid
}

test_expect_success setup '
	git init --bare "$bare" &&
	create_commits_in "$bare" A B C D E F G H I J K &&
	(
		cd "$bare" &&
		git update-ref refs/heads/test $B &&
		git tag -m v1.0 v1.0 $C &&
		git tag -m v2.0 v2.0 $D
	)
'

test_expect_success "local clone" '
	rm -rf work &&
	git clone "$bare" work &&
	(
		cd work &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/heads/master
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/remotes/origin/HEAD
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/remotes/origin/master
	ce858e653cdbf70f9955a39d73a44219e4b92e9e refs/remotes/origin/test
	1c9e58674888f12fae202d3d17075c1bf0b1758b refs/tags/v1.0
	aecf9ddeee5c50b1a54bca444e0299d8096e5ac7 refs/tags/v2.0
	EOF
	test_cmp expect actual	
'

test_expect_success "clone --no-local" '
	rm -rf work &&
	git clone --no-local "$bare" work &&
	(
		cd work &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/heads/master
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/remotes/origin/HEAD
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/remotes/origin/master
	ce858e653cdbf70f9955a39d73a44219e4b92e9e refs/remotes/origin/test
	1c9e58674888f12fae202d3d17075c1bf0b1758b refs/tags/v1.0
	aecf9ddeee5c50b1a54bca444e0299d8096e5ac7 refs/tags/v2.0
	EOF
	test_cmp expect actual	
'

test_expect_success "clone --no-local --black-hole" '
	rm -rf work &&
	git clone --no-local --black-hole "$bare" work >out 2>&1 &&
	tail -1 out >actual &&
	cat >expect<<-EOF &&
	NOTE: read total 1217 bytes of pack data from server.
	EOF
	test_cmp expect actual
'

test_expect_success "nothing saved to disk" '
	find work/.git/objects -type f >actual &&
	cat >expect<<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "clone --no-local --black-hole-verify" '
	rm -rf work &&
	git clone --no-local --black-hole-verify "$bare" work
'

test_expect_success "nothing saved to disk" '
	find work/.git/objects -type f >actual &&
	cat >expect<<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "clone --no-local --black-hole --mirror" '
	rm -rf work &&
	git clone --no-local --black-hole --mirror "$bare" work >out 2>&1 &&
	tail -1 out >actual &&
	cat >expect<<-EOF &&
	NOTE: read total 1217 bytes of pack data from server.
	EOF
	test_cmp expect actual
'

test_expect_success "nothing saved to disk" '
	find work/objects -type f >actual &&
	cat >expect<<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "clone --no-local --black-hole-verify --mirror" '
	rm -rf work &&
	git clone --no-local --black-hole-verify --mirror "$bare" work
'

test_expect_success "nothing saved to disk" '
	find work/objects -type f >actual &&
	cat >expect<<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "normal fetch" '
	rm -rf work &&
	git init work &&
	(
		cd work &&
		git remote add origin "../$bare" &&
		git fetch origin &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/remotes/origin/master
	ce858e653cdbf70f9955a39d73a44219e4b92e9e refs/remotes/origin/test
	1c9e58674888f12fae202d3d17075c1bf0b1758b refs/tags/v1.0
	aecf9ddeee5c50b1a54bca444e0299d8096e5ac7 refs/tags/v2.0
	EOF
	test_cmp expect actual	
'

test_expect_success "normal fetch in bare repo" '
	rm -rf work &&
	git init --bare work &&
	(
		cd work &&
		git remote add --mirror origin "../$bare" &&
		git fetch origin &&
		git show-ref
	) >actual &&
	cat >expect<<-EOF &&
	7fe2e5895c33c91a8482936e104f31bd7b298fec refs/heads/master
	ce858e653cdbf70f9955a39d73a44219e4b92e9e refs/heads/test
	1c9e58674888f12fae202d3d17075c1bf0b1758b refs/tags/v1.0
	aecf9ddeee5c50b1a54bca444e0299d8096e5ac7 refs/tags/v2.0
	EOF
	test_cmp expect actual	
'

test_expect_success "fetch --black-hole" '
	rm -rf work &&
	git init --bare work &&
	(
		cd work &&
		git remote add origin "../$bare" &&
		git fetch --black-hole origin
	) >out 2>&1 &&
	tail -1 out >actual &&
	cat >expect<<-EOF &&
	NOTE: read total 1205 bytes of pack data from server.
	EOF
	test_cmp expect actual
'

test_expect_success "nothing saved to disk" '
	find work/objects -type f >actual &&
	cat >expect<<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "fetch --black-hole-verify" '
	rm -rf work &&
	git init --bare work &&
	(
		cd work &&
		git remote add origin "../$bare" &&
		git fetch --black-hole-verify origin
	)
'

test_expect_success "nothing saved to disk" '
	find work/objects -type f >actual &&
	cat >expect<<-EOF &&
	EOF
	test_cmp expect actual
'

test_done
