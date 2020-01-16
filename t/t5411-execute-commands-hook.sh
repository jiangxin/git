#!/bin/sh
#
# Copyright (c) 2018-2020 Jiang Xin
#

test_description='Test execute-commands hook on special git-push refspec'

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

	# Enable push options for bare.git.
	git -C $bare config receive.advertisePushOptions true &&

	git clone --no-local $bare work &&
	create_commits_in work A B
'

test_expect_success "setup hooks" '
	## execute-commands--pre-receive hook
	cat >$bare/hooks/execute-commands--pre-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: execute-commands--pre-receive\n"

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done
	EOF

	## execute-commands hook
	cat >$bare/hooks/execute-commands <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: execute-commands\n"

	if test \$# -gt 0 && test "\$1" = "--pre-receive"
	then
		printf >&2 ">> pre-receive mode\n"
	fi

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done
	EOF

	## pre-receive hook
	cat >$bare/hooks/pre-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: pre-receive hook\n"

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done
	EOF

	## post-receive hook
	cat >$bare/hooks/post-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: post-receive hook\n"

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done
	EOF
	chmod a+x \
		$bare/hooks/pre-receive \
		$bare/hooks/post-receive \
		$bare/hooks/execute-commands \
		$bare/hooks/execute-commands--pre-receive
'

test_expect_success "create initial branches" '
	(
		cd work &&
		git update-ref HEAD $A &&
		git push origin HEAD HEAD:maint HEAD:a/b/c 2>&1
	) >out &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: pre-receive hook
	remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/master.
	remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/maint.
	remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/a/b/c.
	remote: execute: post-receive hook
	remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/master.
	remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/maint.
	remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/a/b/c.
	EOF
	test_cmp expect actual
'

test_expect_success "create local topic branch" '
	(
		cd work &&
		git checkout -b my/topic origin/master
	)
'

test_expect_success "push to refs/for/master" '
	(
		cd work &&
		git update-ref HEAD $B &&
		git push origin HEAD:refs/for/master/my/topic
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands--pre-receive
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: execute: execute-commands
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: execute: post-receive hook
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	EOF
	test_cmp expect actual
'

test_expect_success "push to refs/for/a/b/c (call execute-commands --pre-receive)" '
	mv $bare/hooks/execute-commands--pre-receive $bare/hooks/execute-commands--pre-receive.ok &&
	(
		cd work &&
		git push origin HEAD:refs/for/a/b/c/my/topic
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/a/b/c/my/topic.
	remote: execute: execute-commands
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/a/b/c/my/topic.
	remote: execute: post-receive hook
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/a/b/c/my/topic.
	EOF
	test_cmp expect actual
'

test_expect_success "push to two special references" '
	(
		cd work &&
		git push origin \
			HEAD:refs/for/maint/my/topic \
			HEAD:refs/for/a/b/c/my/topic
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/a/b/c/my/topic.
	remote: execute: execute-commands
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/a/b/c/my/topic.
	remote: execute: post-receive hook
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/a/b/c/my/topic.
	EOF
	test_cmp expect actual
'

test_expect_success "push to a normal and a special references" '
	(
		cd work &&
		git push origin \
			HEAD:refs/for/maint/my/topic \
			HEAD:refs/heads/master
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	remote: execute: pre-receive hook
	remote: >> old: 102939797ab91a4f201d131418d2c9d919dcdd2c, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/heads/master.
	remote: execute: execute-commands
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	remote: execute: post-receive hook
	remote: >> old: 102939797ab91a4f201d131418d2c9d919dcdd2c, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/heads/master.
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	EOF
	test_cmp expect actual
'

test_expect_success "restore master branch of bare repo" '
	(
		cd $bare &&
		git update-ref refs/heads/master $A $B &&
		git show-ref
	) >actual &&
	cat >expect <<-EOF &&
	102939797ab91a4f201d131418d2c9d919dcdd2c refs/heads/a/b/c
	102939797ab91a4f201d131418d2c9d919dcdd2c refs/heads/maint
	102939797ab91a4f201d131418d2c9d919dcdd2c refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "hooks: update execute-commands (declined version)" '
	mv $bare/hooks/execute-commands $bare/hooks/execute-commands.ok &&
	cat >$bare/hooks/execute-commands <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: execute-commands\n"

	if test \$# -gt 0 && test "\$1" = "--pre-receive"
	then
		printf >&2 ">> pre-receive mode\n"
	fi

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done

	if test \$# -gt 0 && test "\$1" = "--pre-receive"
	then
		printf >&2 ">> ERROR: declined in execute-commands--pre-receive\n"
		exit 1
	fi
	EOF
	chmod a+x $bare/hooks/execute-commands
'

test_expect_success "push to two special references (execute-commands declined)" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/my/topic \
			HEAD:refs/for/maint/my/topic
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/maint/my/topic.
	remote: >> ERROR: declined in execute-commands--pre-receive
	EOF
	test_cmp expect actual
'

test_expect_success "push to mixed references (execute-commands declined)" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/my/topic \
			HEAD:refs/heads/master
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: >> ERROR: declined in execute-commands--pre-receive
	EOF
	test_cmp expect actual
'

test_expect_success "hooks: update pre-receive hook (declined version)" '
	mv $bare/hooks/execute-commands $bare/hooks/execute-commands.fail &&
	mv $bare/hooks/execute-commands.ok $bare/hooks/execute-commands &&
	mv $bare/hooks/pre-receive $bare/hooks/pre-receive.ok &&
	cat >$bare/hooks/pre-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: pre-receive hook\n"

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done
	printf >&2 ">> ERROR: declined in pre-receive hook\n"
	exit 1
	EOF
	chmod a+x $bare/hooks/pre-receive
'

test_expect_success "push to mixed references (pre-creceive declined)" '
	(
		cd work &&
		test_must_fail git push origin \
			HEAD:refs/for/master/my/topic \
			HEAD:refs/heads/master
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: execute: pre-receive hook
	remote: >> old: 102939797ab91a4f201d131418d2c9d919dcdd2c, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/heads/master.
	remote: >> ERROR: declined in pre-receive hook
	EOF
	test_cmp expect actual
'

test_expect_success "hooks: update hooks to show envs" '
	## execute-commands hook
	mv $bare/hooks/execute-commands $bare/hooks/execute-commands.ok &&
	cat >$bare/hooks/execute-commands <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: execute-commands\n"

	if test \$# -gt 0 && test "\$1" = "--pre-receive"
	then
		printf >&2 ">> pre-receive mode\n"
	else
		printf "GIT_VAR1=var1\n"
		printf "GIT_VAR2=var2\n"
		printf "AGIT_VAR1=foo\n"
		printf "AGIT_VAR2=bar\n"
	fi

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done

	for k in GIT_VAR1 GIT_VAR2 AGIT_VAR1 AGIT_VAR2
	do
		if test -n "\$(eval echo \\"\\\$\$k\")"
		then
			printf >&2 ">> has env: \$k=\$(eval echo \\"\\\$\$k\").\n"
		fi
	done
	EOF
	chmod a+x $bare/hooks/execute-commands &&

	## post-receive hook
	mv $bare/hooks/post-receive $bare/hooks/post-receive.ok &&
	cat >$bare/hooks/post-receive <<-EOF &&
	#!/bin/sh

	printf >&2 "execute: post-receive hook\n"

	while read old new ref
	do
		printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
	done

	for k in GIT_VAR1 GIT_VAR2 AGIT_VAR1 AGIT_VAR2
	do
		if test -n "\$(eval echo \\"\\\$\$k\")"
		then
			printf >&2 ">> has env: \$k=\$(eval echo \\"\\\$\$k\").\n"
		fi
	done
	EOF
	chmod a+x $bare/hooks/post-receive
'

test_expect_success "push and show envs" '
	(
		cd work &&
		git push origin \
			HEAD:refs/for/master/my/topic
	) >out 2>&1 &&
	grep "^remote:" out | sed -e "s/  *\$//g" >actual &&
	cat >expect <<-EOF &&
	remote: execute: execute-commands
	remote: >> pre-receive mode
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: execute: execute-commands
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: execute: post-receive hook
	remote: >> old: 0000000000000000000000000000000000000000, new: ce858e653cdbf70f9955a39d73a44219e4b92e9e, ref: refs/for/master/my/topic.
	remote: >> has env: AGIT_VAR1=foo.
	remote: >> has env: AGIT_VAR2=bar.
	EOF
	test_cmp expect actual
'

test_done
