#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test repository lock by pre-check-hook for ref_transaction_commit'

GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main
export GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME

. ./test-lib.sh

bare=a/b/c/bare-repo.git
lockfile=agit-repo.lock

test_create_lock () {
	if test $# -ne 1
	then
		BUG "not 1 parameter to test_create_lock: $@"
	fi &&
	test_path_is_dir "$1" &&
	cat >"$1/$lockfile" <<-\EOF
		lock for maintainance.
	EOF
}

test_remove_lock () {
	if test $# -ne 1
	then
		BUG "not 1 parameter to test_remove_lock: $@"
	fi &&
	test_path_is_dir "$repo" &&
	rm -f "$1/$lockfile"
}

create_bare_repo () {
	test "$#" = 1 ||
	BUG "not 1 parameter to test-create-repo"
	repo="$1"
	mkdir -p "$repo"
	(
		cd "$repo" || error "Cannot setup test environment"
		git -c \
			init.defaultBranch="${GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME-master}" \
			init --bare \
			"--template=$GIT_BUILD_DIR/templates/blt/" >&3 2>&4 ||
		error "cannot run git init -- have you built things yet?"
		mv hooks hooks-disabled &&
		git config core.abbrev 7
	) || exit
}

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
		suffix=${oid#???????} &&
		eval $name=$oid &&
		parent=$oid &&
		shift ||
		return 1
	done &&
	env GIT_REFS_TXN_NO_HOOK=1 \
		git -C "$repo" update-ref refs/heads/main $oid
}

# Format the output of git-push, git-show-ref and other commands to make a
# user-friendly and stable text.  We can easily prepare the expect text
# without having to worry about future changes of the commit ID and spaces
# of the output.  Single quotes are replaced with double quotes, because
# it is boring to prepare unquoted single quotes in expect text.  We also
# remove some locale error messages. The emitted human-readable errors are
# redundant to the more machine-readable output the tests already assert.
make_user_friendly_and_stable_output () {
	sed \
		-e "s/${A:-undef_rev}/<COMMIT-A>/g" \
		-e "s/${B:-undef_rev}/<COMMIT-B>/g" \
		-e "s/${C:-undef_rev}/<COMMIT-C>/g" \
		-e "s/${D:-undef_rev}/<COMMIT-D>/g" \
		-e "s/${E:-undef_rev}/<COMMIT-E>/g" \
		-e "s/${F:-undef_rev}/<COMMIT-F>/g" \
		-e "s/${H:-undef_rev}/<COMMIT-H>/g" \
		-e "s/${I:-undef_rev}/<COMMIT-I>/g" \
		-e "s/${J:-undef_rev}/<COMMIT-J>/g" \
		-e "s/${K:-undef_rev}/<COMMIT-K>/g" \
		-e "s/${TAG1_0:-undef_rev}/<TAG-1-0>/g" \
		-e "s/${TAG1_1:-undef_rev}/<TAG-1-1>/g" \
		-e "s/${TAG1_2:-undef_rev}/<TAG-1-2>/g" \
		-e "s/${TAG1_3:-undef_rev}/<TAG-1-3>/g"
}

test_expect_success setup '
	create_bare_repo "$bare" &&
	create_commits_in "$bare" A B C D E F
'

test_expect_success "fail to update-ref (lock in repo)" '
	test_when_finished "test_remove_lock $bare" &&
	test_create_lock $bare &&
	test_must_fail git -C "$bare" update-ref \
		refs/heads/main $A >actual 2>&1 &&

	cat >expect <<-EOF &&
		error: cannot write to repository, locked by file '"'"'agit-repo.lock'"'"'

		lock for maintainance.

		fatal: ref updates aborted by hook
	EOF
	test_cmp expect actual
'

test_expect_success "update main branch" '
	git -C "$bare" update-ref refs/heads/main $A &&
	git -C "$bare" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect<<-EOF &&
		<COMMIT-A> refs/heads/main
	EOF
	test_cmp expect actual
'

test_expect_success "pack-refs works with lock" '
	test_when_finished "test_remove_lock $bare" &&
	test_create_lock $bare &&
	test_path_is_missing $bare/packed-refs &&
	test_path_is_file $bare/refs/heads/main &&
	git -C $bare pack-refs --all &&
	test_path_is_file $bare/packed-refs &&
	test_path_is_missing $bare/refs/heads/main
'

test_expect_success "fail to create tag (lock in parent dir)" '
	test_when_finished "test_remove_lock \"$HOME\"" &&
	test_create_lock "$HOME" &&

	test_path_is_missing $bare/$lockfile &&
	test_path_is_file "$HOME/$lockfile" &&

	test_must_fail git -C $bare tag -m v1.0 \
		v1.0 refs/heads/main >actual 2>&1 &&
	cat >expect <<-\EOF &&
		error: cannot write to repository, locked by file '"'"'agit-repo.lock'"'"'

		lock for maintainance.

		fatal: ref updates aborted by hook
	EOF
	test_cmp expect actual
'

test_expect_success "create tag" '
	(
		cd "$bare" &&
		test_tick &&
		git tag -m v1.0 v1.0 refs/heads/main &&
		test_path_is_file refs/tags/v1.0
	)
'
test_expect_success "gc works with lock" '
	test_when_finished "test_remove_lock \"$HOME\"" &&
	test_create_lock "$HOME" &&
	(
		cd "$bare" &&
		test_path_is_file refs/tags/v1.0 &&
		git gc -q &&
		test_path_is_missing refs/tags/v1.0
	)
'

test_expect_success "prepare workdir" '
	git clone --no-local "$bare" work &&
	create_commits_in work H I J K &&
	(
		cd work &&
		test_tick &&
		git tag -m v1.1 v1.1 $H &&
		git tag -m v1.2 v1.2 $I &&
		git tag -m v1.3 v1.3 $J &&
		git branch dev $K
	) &&
	eval TAG1_0=$(git -C work rev-parse v1.0) &&
	eval TAG1_1=$(git -C work rev-parse v1.1) &&
	eval TAG1_2=$(git -C work rev-parse v1.2) &&
	eval TAG1_3=$(git -C work rev-parse v1.3)
'

test_expect_success "fail to push one ref (lock in HOME)" '
	test_when_finished "test_remove_lock \"$HOME\"" &&
	test_create_lock "$HOME" &&

	test_must_fail git -C work push origin v1.1 \
		>out 2>&1 &&
	grep -q "fatal: ref updates aborted by hook" out
'

test_expect_success "fail to push multiple refs (lock in HOME)" '
	test_when_finished "test_remove_lock \"$HOME\"" &&
	test_create_lock "$HOME" &&

	test_must_fail git -C work push origin \
		v1.1 v1.2 v1.3 dev >out 2>&1 &&
	grep -q "fatal: ref updates aborted by hook" out &&
	git -C "$bare" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect<<-EOF &&
		<COMMIT-A> refs/heads/main
		<TAG-1-0> refs/tags/v1.0
	EOF
	test_cmp expect actual
'

test_expect_success "no lock, push ok" '
	test_remove_lock "$HOME" &&
	git -C work push origin v1.1 v1.2 v1.3 dev &&
	git -C "$bare" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect<<-EOF &&
		<COMMIT-K> refs/heads/dev
		<COMMIT-A> refs/heads/main
		<TAG-1-0> refs/tags/v1.0
		<TAG-1-1> refs/tags/v1.1
		<TAG-1-2> refs/tags/v1.2
		<TAG-1-3> refs/tags/v1.3
	EOF
	test_cmp expect actual
'

test_done
