#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test rate limit for repository push'
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
	git clone --no-local $bare workcopy &&
	create_commits_in workcopy A B C
'

test_expect_success "push ok without rate limit" '
	rm -r "$bare" &&
	git init --bare $bare &&
	(
		cd workcopy &&
		env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=30 \
			git push origin HEAD
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" \
		-e "s/  *$//g" \
		-e "s/fetch-pack [0-9][0-9]* on [a-zA-Z0-9._-]*/fetch-pack <pid> on <host>/g" \
		-e "s#agent=git/[^ ]*#agent=git/x.x.x#g" \
		-e "s#/.*/bare.git#/path/to/bare.git#g" \
		< out >actual &&
	cat >expect <<-EOF &&
	To /path/to/bare.git
	 * [new branch]      HEAD -> master
	EOF
	test_cmp expect actual &&
	(
		cd $bare &&
		git log master --oneline
	) >actual &&
	cat >expect <<-EOF &&
	5e25abc C
	ce858e6 B
	1029397 A
	EOF
	test_cmp expect actual
'

test_expect_success "push failed: hard limit" '
	rm -r "$bare" &&
	git init --bare $bare &&
	(
		cd workcopy &&
		test_must_fail env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=220,350,500 \
			git push origin HEAD
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" \
		-e "s/  *$//g" \
		-e "s/fetch-pack [0-9][0-9]* on [a-zA-Z0-9._-]*/fetch-pack <pid> on <host>/g" \
		-e "s#agent=git/[^ ]*#agent=git/x.x.x#g" \
		-e "s#/.*/bare.git#/path/to/bare.git#g" \
		< out | grep -v "^fatal:" >actual &&
	grep "^fatal:" out >actual.fatal &&
	cat >expect <<-EOF &&
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: ERROR: Server load (500%) is too high, quilt
	
	EOF
	cat >expect.fatal <<-EOF &&
	fatal: failed to wait_for_avail_loadavg
	fatal: the remote end hung up unexpectedly
	EOF
	test_cmp expect actual &&
	find $bare/objects -type f >actual 2>&1 &&
	cat >expect <<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "push fail: all soft limit" '
	rm -r "$bare" &&
	git init --bare $bare &&
	(
		cd workcopy &&
		test_must_fail env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=220,350 \
			git push origin HEAD
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" \
		-e "s/  *$//g" \
		-e "s/fetch-pack [0-9][0-9]* on [a-zA-Z0-9._-]*/fetch-pack <pid> on <host>/g" \
		-e "s#agent=git/[^ ]*#agent=git/x.x.x#g" \
		-e "s#/.*/bare.git#/path/to/bare.git#g" \
		< out | grep -v "^fatal:" >actual &&
	grep "^fatal:" out >actual.fatal &&
	cat >expect <<-EOF &&
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 3/3]...
	remote: WARN: Will sleep xx seconds...
	remote: ERROR: Server load (350%) is still high, quilt
	
	EOF
	cat >expect.fatal <<-EOF &&
	fatal: failed to wait_for_avail_loadavg
	fatal: the remote end hung up unexpectedly
	EOF
	test_cmp expect actual &&
	test_cmp expect.fatal actual.fatal &&
	find $bare/objects -type f >actual 2>&1 &&
	cat >expect <<-EOF &&
	EOF
	test_cmp expect actual
'

test_expect_success "push ok: 3 soft limit, and ok" '
	rm -r "$bare" &&
	git init --bare $bare &&
	(
		cd workcopy &&
		env \
			AGIT_LOADAVG_SOFT_LIMIT=200 \
			AGIT_LOADAVG_HARD_LIMIT=400 \
			AGIT_LOADAVG_RETRY=3 \
			AGIT_LOADAVG_TEST_DRYRUN=1 \
			AGIT_LOADAVG_TEST_MOCK=220,350,380,100 \
			git push origin HEAD
	) >out 2>&1 &&
	sed -e "s/[0-9][0-9]* seconds/xx seconds/g" \
		-e "s/  *$//g" \
		-e "s/fetch-pack [0-9][0-9]* on [a-zA-Z0-9._-]*/fetch-pack <pid> on <host>/g" \
		-e "s#agent=git/[^ ]*#agent=git/x.x.x#g" \
		-e "s#/.*/bare.git#/path/to/bare.git#g" \
		< out >actual &&
	cat >expect <<-EOF &&
	remote: WARN: Server load (220%) is high, waiting xx seconds [loop 1/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (350%) is high, waiting xx seconds [loop 2/3]...
	remote: WARN: Will sleep xx seconds...
	remote: WARN: Server load (380%) is high, waiting xx seconds [loop 3/3]...
	remote: WARN: Will sleep xx seconds...
	To /path/to/bare.git
	 * [new branch]      HEAD -> master
	EOF
	test_cmp expect actual &&
	(
		cd $bare &&
		git log master --oneline
	) >actual &&
	cat >expect <<-EOF &&
	5e25abc C
	ce858e6 B
	1029397 A
	EOF
	test_cmp expect actual
'

test_done
