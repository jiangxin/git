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

test_done
