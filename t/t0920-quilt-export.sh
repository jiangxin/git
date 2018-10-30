#!/bin/sh
#
# Copyright (c) 2019 Jiang Xin
#

test_description='Test git quiltexport'

. ./test-lib.sh

bare=bare.git

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
	shift &&
	while test $# -gt 0
	do
		name=$1 &&
		H=$(echo $name | git -C "$repo" hash-object --stdin -t blob -w)
		T=$(
			(if test -n "$parent"; then
				git -C "$repo" ls-tree $parent
			 fi; printf "100644 blob $H\t$name.txt\n") |
			git -C "$repo" mktree
		) &&
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
	create_commits_in "$bare" A B C D E F &&
	(
		cd "$bare" &&
		git update-ref refs/heads/test $B &&
		git tag -m v1.0 v1.0 $C &&
		git tag -m v2.0 v2.0 $D
	)
'

test_expect_success "clone" '
	git clone "$bare" work
'

test_expect_success "git rev-list \$D..HEAD" '
	git -C work log --oneline $D..HEAD >actual &&
	cat >expect<<-EOF &&
	785c77c F
	9e97dcc E
	EOF
	test_cmp expect actual
'

test_expect_success "git quiltexport \$D" '
	git -C work quiltexport $D &&
	cat >expect<<-EOF &&
	t/0001-E.patch
	t/0002-F.patch
	EOF
	test_cmp expect work/patches/series
'

test_expect_success "patch files exist" '
	test -s work/patches/t/0001-E.patch &&
	test -s work/patches/t/0002-F.patch &&
	test -s work/patches/series
'

test_expect_success "git quiltexport ^\$B" '
	git -C work quiltexport --patches patches-02 ^$B &&
	cat >expect<<-EOF &&
	t/0001-C.patch
	t/0002-D.patch
	t/0003-E.patch
	t/0004-F.patch
	EOF
	test_cmp expect work/patches-02/series &&
	test -f work/patches-02/t/0001-C.patch &&
	test -f work/patches-02/t/0002-D.patch &&
	test -f work/patches-02/t/0003-E.patch &&
	test -f work/patches-02/t/0004-F.patch
'

test_expect_success "git quiltexport v2.0 ^v1.0" '
	(
		cd work &&
		git quiltexport --patches patches-03 v2.0 ^v1.0
	) &&
	cat >expect<<-EOF &&
	t/0001-D.patch
	EOF
	test_cmp expect work/patches-03/series &&
	test -f work/patches-03/t/0001-D.patch
'

test_expect_success "git quiltexport \$A..v2.0" '
	(
		cd work &&
		git quiltexport --patches patches-04 $A..v2.0
	) &&
	cat >expect<<-EOF &&
	t/0001-B.patch
	t/0002-C.patch
	t/0003-D.patch
	EOF
	test_cmp expect work/patches-04/series &&
	test -f work/patches-04/t/0001-B.patch &&
	test -f work/patches-04/t/0002-C.patch &&
	test -f work/patches-04/t/0003-D.patch
'

test_expect_success "git quiltexport --not \$1.0 --not \$v2.0" '
	(
		cd work &&
		git quiltexport --patches patches-05 -- --not $B --not $D
	) &&
	cat >expect<<-EOF &&
	t/0001-C.patch
	t/0002-D.patch
	EOF
	test_cmp expect work/patches-05/series &&
	test -f work/patches-05/t/0001-C.patch &&
	test -f work/patches-05/t/0002-D.patch
'

test_done
