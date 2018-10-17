#!/bin/sh
#
# Copyright (c) 2020 Jiang Xin
#

test_description='Test proc-receive hook'

. ./test-lib.sh

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

format_git_output () {
	sed \
		-e "s/  *\$//g" \
		-e "s#/.*/bare.git#path/of/repo.git#g" \
		-e "s/'/\"/g"
}

# Asynchronous sideband may generate inconsistent output messages,
# sort before comparison.
test_sorted_cmp () {
	if ! $GIT_TEST_CMP "$@"
	then
		cmd=$GIT_TEST_CMP 
		for f in "$@"
		do
			sort "$f" >"$f.sorted"
			cmd="$cmd \"$f.sorted\""
		done
		if ! eval $cmd
		then
			$GIT_TEST_CMP "$@"
		fi
	fi
}

test_expect_success "setup" '
	git init --bare bare.git &&
	git clone --no-local bare.git work &&
	create_commits_in work A B &&
	(
		cd work &&
		git config core.abbrev 7 &&
		git update-ref refs/heads/master $A &&
		test_tick &&
		git tag -m "v1.0.0" v1.0.0 $A &&
		git push origin \
			$B:refs/heads/master \
			$A:refs/heads/next
	) &&
	TAG=$(cd work; git rev-parse v1.0.0) &&

	# setup pre-receive hook
	cat >bare.git/hooks/pre-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "# pre-receive hook\n"

	while read old new ref
	do
		printf >&2 "pre-receive< \$old \$new \$ref\n"
	done
	EOF

	# setup post-receive hook
	cat >bare.git/hooks/post-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "# post-receive hook\n"

	while read old new ref
	do
		printf >&2 "post-receive< \$old \$new \$ref\n"
	done
	EOF

	chmod a+x \
		bare.git/hooks/pre-receive \
		bare.git/hooks/post-receive
'

test_expect_success "normal git-push command" '
	(
		cd work &&
		git push -f origin \
			refs/tags/v1.0.0 \
			:refs/heads/next \
			HEAD:refs/heads/master \
			HEAD:refs/review/master/topic \
			HEAD:refs/heads/a/b/c
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $B $A refs/heads/master
	remote: pre-receive< $A $ZERO_OID refs/heads/next
	remote: pre-receive< $ZERO_OID $TAG refs/tags/v1.0.0
	remote: pre-receive< $ZERO_OID $A refs/review/master/topic
	remote: pre-receive< $ZERO_OID $A refs/heads/a/b/c
	remote: # post-receive hook
	remote: post-receive< $B $A refs/heads/master
	remote: post-receive< $A $ZERO_OID refs/heads/next
	remote: post-receive< $ZERO_OID $TAG refs/tags/v1.0.0
	remote: post-receive< $ZERO_OID $A refs/review/master/topic
	remote: post-receive< $ZERO_OID $A refs/heads/a/b/c
	To path/of/repo.git
	 + ce858e6...1029397 HEAD -> master (forced update)
	 - [deleted]         next
	 * [new tag]         v1.0.0 -> v1.0.0
	 * [new reference]   HEAD -> refs/review/master/topic
	 * [new branch]      HEAD -> a/b/c
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/a/b/c
	$A refs/heads/master
	$A refs/review/master/topic
	$TAG refs/tags/v1.0.0
	EOF
	test_cmp expect actual
'

test_expect_success "cleanup" '
	(
		cd bare.git &&
		git update-ref -d refs/review/master/topic &&
		git update-ref -d refs/tags/v1.0.0 &&
		git update-ref -d refs/heads/a/b/c
	)
'

test_expect_success "add two receive.procReceiveRefs settings" '
	(
		cd bare.git &&
		git config --add receive.procReceiveRefs refs/for/ &&
		git config --add receive.procReceiveRefs refs/review/
	)
'

test_expect_success "no proc-receive hook, fail to push special ref" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:next \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/heads/next
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: error: cannot to find hook "proc-receive"
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/heads/next
	To path/of/repo.git
	 * [new branch]      HEAD -> next
	 ! [remote rejected] HEAD -> refs/for/master/topic (fail to run proc-receive hook)
	error: failed to push some refs to "path/of/repo.git"
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	$A refs/heads/next
	EOF
	test_cmp expect actual
'

test_expect_success "cleanup" '
	(
		cd bare.git &&
		git update-ref -d refs/heads/next
	)
'

test_expect_success "no proc-receive hook, fail all for atomic push" '
	(
		cd work &&
		test_must_fail git push --atomic origin \
			HEAD:next \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/heads/next
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: error: cannot to find hook "proc-receive"
	To path/of/repo.git
	 ! [rejected]        master (atomic push failed)
	 ! [remote rejected] HEAD -> next (fail to run proc-receive hook)
	 ! [remote rejected] HEAD -> refs/for/master/topic (fail to run proc-receive hook)
	error: failed to push some refs to "path/of/repo.git"
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (bad version)" '
	cat >bare.git/hooks/proc-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v --version 2
	EOF
	chmod a+x bare.git/hooks/proc-receive
'

test_expect_success "pro-receive bad protocol: unknown version" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	fatal: protocol error: unknown proc-receive version "2"
	fatal: the remote end hung up unexpectedly
	fatal: the remote end hung up unexpectedly
	EOF
	test_sorted_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (no report)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v
	EOF
'

test_expect_success "pro-receive bad protocol: no report" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	To path/of/repo.git
	 ! [remote failure]  HEAD -> refs/for/master/topic (remote failed to report status)
	error: failed to push some refs to "path/of/repo.git"
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (bad oid)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "bad-id new-id ref ok"
	EOF
'

test_expect_success "pro-receive bad protocol: bad oid" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> bad-id new-id ref ok
	fatal: protocol error: proc-receive expected "old new ref status [msg]", got "bad-id new-id ref ok"
	fatal: the remote end hung up unexpectedly
	fatal: the remote end hung up unexpectedly
	EOF
	test_sorted_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (no status)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic"
	EOF
'

test_expect_success "pro-receive bad protocol: no status" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic
	fatal: protocol error: proc-receive expected "old new ref status [msg]", got "$ZERO_OID $A refs/for/master/topic"
	fatal: the remote end hung up unexpectedly
	fatal: the remote end hung up unexpectedly
	EOF
	test_sorted_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (unknown status)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic xx msg"
	EOF
'

test_expect_success "pro-receive bad protocol: unknown status" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic xx msg
	fatal: protocol error: proc-receive has bad status "xx" for "$ZERO_OID $A refs/for/master/topic"
	fatal: the remote end hung up unexpectedly
	fatal: the remote end hung up unexpectedly
	EOF
	test_sorted_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (bad status)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic bad status"
	EOF
'

test_expect_success "pro-receive bad protocol: bad status" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic bad status
	fatal: protocol error: proc-receive has bad status "bad status" for "$ZERO_OID $A refs/for/master/topic"
	fatal: the remote end hung up unexpectedly
	fatal: the remote end hung up unexpectedly
	EOF
	test_sorted_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (ng)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic ng"
	EOF
'

test_expect_success "pro-receive: fail to update (no message)" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ng
	To path/of/repo.git
	 ! [remote rejected] HEAD -> refs/for/master/topic (failed)
	error: failed to push some refs to "path/of/repo.git"
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (ng message)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic ng error msg"
	EOF
'

test_expect_success "pro-receive: fail to update (has message)" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ng error msg
	To path/of/repo.git
	 ! [remote rejected] HEAD -> refs/for/master/topic (error msg)
	error: failed to push some refs to "path/of/repo.git"
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (ok)" '
	cat >bare.git/hooks/proc-receive <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic ok"
	EOF
'

test_expect_success "pro-receive: ok" '
	(
		cd work &&
		git push origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/for/master/topic
	To path/of/repo.git
	 * [new reference]   HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "pro-receive: report unknown ref" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/a/b/c/my/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/a/b/c/my/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/a/b/c/my/topic
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ok
	warning: remote reported status on unknown ref: refs/for/master/topic
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/for/master/topic
	To path/of/repo.git
	 ! [remote failure]  HEAD -> refs/for/a/b/c/my/topic (remote failed to report status)
	error: failed to push some refs to "path/of/repo.git"
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "not support push options" '
	(
		cd work &&
		test_must_fail git push \
			-o issue=123 \
			-o reviewer=user1 \
			origin \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	fatal: the receiving end does not support push options
	fatal: the remote end hung up unexpectedly
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "enable push options" '
	(
		cd bare.git &&
		git config receive.advertisePushOptions true
	)
'

test_expect_success "push with options" '
	(
		cd work &&
		git push \
			-o issue=123 \
			-o reviewer=user1 \
			origin \
			HEAD:refs/heads/next \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/heads/next
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive< issue=123
	remote: proc-receive< reviewer=user1
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/for/master/topic
	remote: post-receive< $ZERO_OID $A refs/heads/next
	To path/of/repo.git
	 * [new branch]      HEAD -> next
	 * [new reference]   HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	$A refs/heads/next
	EOF
	test_cmp expect actual
'

test_expect_success "cleanup" '
	(
		cd bare.git &&
		git update-ref -d refs/heads/next
	)
'

test_expect_success "setup proc-receive hook" '
	cat >bare.git/hooks/proc-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/next/topic ok" \
		-r "$ZERO_OID $A refs/review/a/b/c/topic ok" \
		-r "$ZERO_OID $A refs/for/master/topic ok"
	EOF
	chmod a+x bare.git/hooks/proc-receive
'

test_expect_success "report test: all special refs" '
	(
		cd work &&
		git push origin \
			HEAD:refs/for/next/topic \
			HEAD:refs/review/a/b/c/topic \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/next/topic
	remote: pre-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/next/topic
	remote: proc-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/next/topic ok
	remote: proc-receive> $ZERO_OID $A refs/review/a/b/c/topic ok
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/for/next/topic
	remote: post-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: post-receive< $ZERO_OID $A refs/for/master/topic
	To path/of/repo.git
	 * [new reference]   HEAD -> refs/for/next/topic
	 * [new reference]   HEAD -> refs/review/a/b/c/topic
	 * [new reference]   HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "report test: mixed refs" '
	(
		cd work &&
		git push origin \
			HEAD:refs/heads/zzz \
			HEAD:refs/heads/yyy \
			HEAD:refs/for/next/topic \
			HEAD:refs/review/a/b/c/topic \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/heads/zzz
	remote: pre-receive< $ZERO_OID $A refs/heads/yyy
	remote: pre-receive< $ZERO_OID $A refs/for/next/topic
	remote: pre-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/next/topic
	remote: proc-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/next/topic ok
	remote: proc-receive> $ZERO_OID $A refs/review/a/b/c/topic ok
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/for/next/topic
	remote: post-receive< $ZERO_OID $A refs/heads/zzz
	remote: post-receive< $ZERO_OID $A refs/heads/yyy
	remote: post-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: post-receive< $ZERO_OID $A refs/for/master/topic
	To path/of/repo.git
	 * [new branch]      HEAD -> zzz
	 * [new branch]      HEAD -> yyy
	 * [new reference]   HEAD -> refs/for/next/topic
	 * [new reference]   HEAD -> refs/review/a/b/c/topic
	 * [new reference]   HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	$A refs/heads/yyy
	$A refs/heads/zzz
	EOF
	test_cmp expect actual
'

test_expect_success "cleanup" '
	(
		cd bare.git &&
		git update-ref -d refs/heads/yyy &&
		git update-ref -d refs/heads/zzz
	)
'

test_expect_success "report test: mixed refs" '
	(
		cd work &&
		git push origin \
			HEAD:refs/for/next/topic \
			HEAD:refs/heads/zzz \
			HEAD:refs/heads/yyy \
			HEAD:refs/review/a/b/c/topic \
			HEAD:refs/for/master/topic
	) >out 2>&1 &&
	format_git_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< $ZERO_OID $A refs/for/next/topic
	remote: pre-receive< $ZERO_OID $A refs/heads/zzz
	remote: pre-receive< $ZERO_OID $A refs/heads/yyy
	remote: pre-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: pre-receive< $ZERO_OID $A refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< $ZERO_OID $A refs/for/next/topic
	remote: proc-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: proc-receive< $ZERO_OID $A refs/for/master/topic
	remote: proc-receive> $ZERO_OID $A refs/for/next/topic ok
	remote: proc-receive> $ZERO_OID $A refs/review/a/b/c/topic ok
	remote: proc-receive> $ZERO_OID $A refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< $ZERO_OID $A refs/for/next/topic
	remote: post-receive< $ZERO_OID $A refs/heads/zzz
	remote: post-receive< $ZERO_OID $A refs/heads/yyy
	remote: post-receive< $ZERO_OID $A refs/review/a/b/c/topic
	remote: post-receive< $ZERO_OID $A refs/for/master/topic
	To path/of/repo.git
	 * [new reference]   HEAD -> refs/for/next/topic
	 * [new branch]      HEAD -> zzz
	 * [new branch]      HEAD -> yyy
	 * [new reference]   HEAD -> refs/review/a/b/c/topic
	 * [new reference]   HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	(
		cd bare.git &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	$A refs/heads/master
	$A refs/heads/yyy
	$A refs/heads/zzz
	EOF
	test_cmp expect actual
'

test_done
