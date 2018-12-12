#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test rate limit for repository fetch'
. ./test-lib.sh

bare=bare.git

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
	git init --bare $bare &&
	create_commits_in $bare A B C
'

test_expect_success "clone ok without rate limit" '
	env \
		AGIT_LOADAVG_SOFT_LIMIT=200 \
		AGIT_LOADAVG_HARD_LIMIT=400 \
		AGIT_LOADAVG_RETRY=3 \
		AGIT_LOADAVG_TEST_DRYRUN=1 \
		AGIT_LOADAVG_TEST_MOCK=30 \
		git clone --no-local $bare workcopy >actual 2>&1 &&
	cat >expect <<-EOF &&
	Cloning into '"'"'workcopy'"'"'...
	EOF
	test_cmp expect actual &&
	test -d workcopy &&
	git -C workcopy log --oneline >actual &&
	cat >expect <<-EOF &&
	5e25abc C
	ce858e6 B
	1029397 A
	EOF
	test_cmp expect actual &&
	rm -rf workcopy
'

test_expect_success "clone failed: hard limit" '
	test_must_fail env \
		AGIT_LOADAVG_SOFT_LIMIT=200 \
		AGIT_LOADAVG_HARD_LIMIT=400 \
		AGIT_LOADAVG_RETRY=3 \
		AGIT_LOADAVG_TEST_DRYRUN=1 \
		AGIT_LOADAVG_TEST_MOCK=220,350,500 \
		git clone --no-local $bare workcopy >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" -e "s/  *$//g" < out >actual &&
	cat >expect <<-EOF &&
	Cloning into '"'"'workcopy'"'"'...
	fatal: failed to wait_for_avail_loadavg
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: ERROR: Server load (500%) is too high, quilt
	
	fatal: early EOF
	fatal: index-pack failed
	EOF
	test_cmp expect actual &&
	test ! -d workcopy
'

test_expect_success "clone failed: all soft limit" '
	test_must_fail env \
		AGIT_LOADAVG_SOFT_LIMIT=200 \
		AGIT_LOADAVG_HARD_LIMIT=400 \
		AGIT_LOADAVG_RETRY=3 \
		AGIT_LOADAVG_TEST_DRYRUN=1 \
		AGIT_LOADAVG_TEST_MOCK=220,350 \
		git clone --no-local $bare workcopy >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" -e "s/  *$//g" < out >actual &&
	cat >expect <<-EOF &&
	Cloning into '"'"'workcopy'"'"'...
	fatal: failed to wait_for_avail_loadavg
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 3/3]...
	remote: WARN: Will sleep xx seconds...
	remote: ERROR: Server load (350%) is still high, quilt
	
	fatal: early EOF
	fatal: index-pack failed
	EOF
	test_cmp expect actual &&
	test ! -d workcopy
'

test_expect_success "clone ok: 3 soft limit, and ok" '
	env \
		AGIT_LOADAVG_SOFT_LIMIT=200 \
		AGIT_LOADAVG_HARD_LIMIT=400 \
		AGIT_LOADAVG_RETRY=3 \
		AGIT_LOADAVG_TEST_DRYRUN=1 \
		AGIT_LOADAVG_TEST_MOCK=220,350,380,100 \
		git clone --no-local $bare workcopy >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" -e "s/  *$//g" < out >actual &&
	cat >expect <<-EOF &&
	Cloning into '"'"'workcopy'"'"'...
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (380%) is high, waiting xx seconds [loop 3/3]...
	remote: WARN: Will sleep xx seconds...
	EOF
	test_cmp expect actual &&
	test -d workcopy
'

test_expect_success "check clone history, and cleanup" '
	(
		cd workcopy &&
		git log --oneline
	) >actual &&
	cat >expect <<-EOF &&
	5e25abc C
	ce858e6 B
	1029397 A
	EOF
	test_cmp expect actual &&
	rm -r workcopy
'

test_expect_success "fetch ok without rate limit" '
	git init workcopy &&
	(
		cd workcopy &&
		git remote add origin ../$bare &&
		env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=30 \
			git fetch origin &&
			git merge --ff-only origin/master
	) >actual 2>&1 &&
	cat >expect <<-EOF &&
	From ../bare
	 * [new branch]      master     -> origin/master
	EOF
	test_cmp expect actual &&
	test -d workcopy &&
	git -C workcopy log --oneline >actual &&
	cat >expect <<-EOF &&
	5e25abc C
	ce858e6 B
	1029397 A
	EOF
	test_cmp expect actual &&
	rm -rf workcopy
'

test_expect_success "fetch failed: hard limit" '
	git init workcopy &&
	(
		cd workcopy &&
		git remote add origin ../$bare &&
		test_must_fail env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=220,350,500 \
			git fetch origin
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" -e "s/  *$//g" < out >actual &&
	cat >expect <<-EOF &&
	fatal: failed to wait_for_avail_loadavg
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: ERROR: Server load (500%) is too high, quilt
	
	fatal: protocol error: bad pack header
	EOF
	test_cmp expect actual &&
	find workcopy/.git/objects -type f >actual &&
	cat >expect <<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "fetch failed: all soft limit" '
	rm -rf workcopy &&
	git init workcopy &&
	(
		cd workcopy &&
		git remote add origin ../$bare &&
		test_must_fail env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=220,350 \
			git fetch origin
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" -e "s/  *$//g" < out >actual &&
	cat >expect <<-EOF &&
	fatal: failed to wait_for_avail_loadavg
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 3/3]...
	remote: WARN: Will sleep xx seconds...
	remote: ERROR: Server load (350%) is still high, quilt
	
	fatal: protocol error: bad pack header
	EOF
	test_cmp expect actual &&
	find workcopy/.git/objects -type f >actual &&
	cat >expect <<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "fetch ok: 3 soft limit, and ok" '
	rm -rf workcopy &&
	git init workcopy &&
	(
		cd workcopy &&
		git remote add origin ../$bare &&
		env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=220,350,380,100 \
			git fetch origin &&
			git merge --ff-only origin/master
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" -e "s/  *$//g" < out >actual &&
	cat >expect <<-EOF &&
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (380%) is high, waiting xx seconds [loop 3/3]...
	remote: WARN: Will sleep xx seconds...
	From ../bare
	 * [new branch]      master     -> origin/master
	EOF
	test_cmp expect actual
'

test_expect_success "check fetched history, and cleanup" '
	(
		cd workcopy &&
		git log --oneline
	) >actual &&
	cat >expect <<-EOF &&
	5e25abc C
	ce858e6 B
	1029397 A
	EOF
	test_cmp expect actual &&
	rm -r workcopy
'

test_done
