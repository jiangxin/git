#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test repository lock by pre-check-hook for ref_transaction_commit'

GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main
export GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME

. ./test-lib.sh

checksum=info/checksum

if type git-checksum
then
	test_set_prereq GIT_CHECKSUM
fi

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

# Create commits in <repo> and assign each commit's oid to shell variables
# given in the arguments (A, B, and C). E.g.:
#
#     create_commits_in <repo> A B C
#
# NOTE: Never calling this function from a subshell since variable
# assignments will disappear when subshell exits.
create_commits_in () {
	local repo="$1" &&
	shift &&
	while test $# -gt 0
	do
		local name=$1 &&
		shift &&
		test_commit -C "$repo" --no-tag "$name" &&
		local rev=$(git -C "$repo" rev-parse HEAD) &&
		eval "$name=$rev" || return 1
	done
}

# Create commits in bare repo.
create_commits_in_bare_repo () {
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
	git -C "$repo" update-ref refs/heads/main $oid
}

get_abbrev_oid () {
	oid=$1 &&
	suffix=${oid#???????} &&
	oid=${oid%$suffix} &&
	if test -n "$oid"
	then
		echo "$oid"
	else
		echo "undefined-oid"
	fi
}

# Format the output of git-push, git-show-ref and other commands to make a
# user-friendly and stable text.  We can easily prepare the expect text
# without having to worry about future changes of the commit ID.
make_user_friendly_and_stable_output () {
	sed \
		-e "s/$(get_abbrev_oid $A)[0-9a-f]*/<COMMIT-A>/g" \
		-e "s/$(get_abbrev_oid $B)[0-9a-f]*/<COMMIT-B>/g" \
		-e "s/$(get_abbrev_oid $C)[0-9a-f]*/<COMMIT-C>/g" \
		-e "s/$(get_abbrev_oid $D)[0-9a-f]*/<COMMIT-D>/g" \
		-e "s/$(get_abbrev_oid $E)[0-9a-f]*/<COMMIT-E>/g" \
		-e "s/$(get_abbrev_oid $F)[0-9a-f]*/<COMMIT-F>/g" \
		-e "s/$(get_abbrev_oid $G)[0-9a-f]*/<COMMIT-G>/g" \
		-e "s/$(get_abbrev_oid $H)[0-9a-f]*/<COMMIT-H>/g" \
		-e "s/$(get_abbrev_oid $I)[0-9a-f]*/<COMMIT-I>/g" \
		-e "s/$ZERO_OID/<ZERO-OID>/g"
}

test_cmp_heads_and_tags () {
	indir= &&
	while test $# != 0
	do
		case "$1" in
		-C)
			indir="$2" &&
			shift
			;;
		*)
			break
			;;
		esac &&
		shift
	done &&
	expect=${1:-expect} &&
	actual=${2:-actual-heads-and-tags} &&
	indir=${indir:+"$indir"/} &&
	test_path_is_file "$expect" &&
	test_when_finished "rm -f \"$actual\"" &&
	git ${indir:+ -C "$indir"} show-ref --heads --tags |
		make_user_friendly_and_stable_output >"$actual" &&
	test_cmp "$expect" "$actual"
}

test_expect_success GIT_CHECKSUM "create an empty checksum before commit" '
	test_when_finished "rm -rf bare.git" &&
	if ! test -z "$test_tick"
	then
		unset test_tick
	fi &&
	create_bare_repo bare.git &&
	test_path_is_missing bare.git/$checksum &&
	touch bare.git/$checksum &&
	create_commits_in_bare_repo bare.git A B C D E F &&
	git -C bare.git checksum >actual &&
	cat >expect<<-\EOF &&
		a00dd5074d5493c2347986e6c40d2faf
	EOF
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "re-create bare repo, no initial checksum, won't create checksum" '
	if ! test -z "$test_tick"
	then
		unset test_tick
	fi &&
	create_bare_repo bare.git &&
	create_commits_in_bare_repo bare.git A B C D E F &&
	test_path_is_missing "bare.git/$checksum" &&
	test_must_fail git -C bare.git checksum >actual 2>&1 &&
	cat >expect<<-\EOF &&
		ERROR: checksum file does not exist, please run `git-checksum --init` to create one
	EOF
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "git checksum --init" '
	git -C bare.git checksum --init &&
	test_path_is_file "bare.git/$checksum" &&
	git -C bare.git checksum >actual &&
	cat >expect<<-\EOF &&
		a00dd5074d5493c2347986e6c40d2faf
	EOF
	test_cmp expect actual &&
	git -C bare.git checksum --verify
'

test_expect_success GIT_CHECKSUM "git pack-ref, won't change checksum" '
	git -C bare.git pack-refs --all &&
	git -C bare.git gc &&
	git -C bare.git checksum >actual &&
	cat >expect<<-\EOF &&
		a00dd5074d5493c2347986e6c40d2faf
	EOF
	test_cmp expect actual &&
	git -C bare.git checksum --verify
'

test_expect_success GIT_CHECKSUM "clone to work" '
	git clone --no-local bare.git work
'

test_expect_success GIT_CHECKSUM "create new branch" '
	(
		cd work &&
		git checkout -b next &&
		git push -u origin HEAD
	) &&
	git -C bare.git show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect<<-\EOF &&
		<COMMIT-F> refs/heads/main
		<COMMIT-F> refs/heads/next
	EOF
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "verify checksum after new branch" '
	git -C bare.git checksum >actual &&
	cat >expect<<-\EOF &&
		e5c68e5ed182b59a72ad65d6f84855ca
	EOF
	test_cmp expect actual &&
	git -C bare.git checksum -V
'

test_expect_success GIT_CHECKSUM "create other not well-known references" '
	(
		cd work &&
		git push -u origin HEAD:refs/tmp/abc123456 &&
		git push -u origin HEAD:refs/keep-around/577711d99f417fdc46fdbd13c1cc6361ed90283d &&
		git push -u origin HEAD:refs/remotes/origin/pu
	) &&
	git -C bare.git show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect<<-\EOF &&
		<COMMIT-F> refs/heads/main
		<COMMIT-F> refs/heads/next
		<COMMIT-F> refs/keep-around/577711d99f417fdc46fdbd13c1cc6361ed90283d
		<COMMIT-F> refs/remotes/origin/pu
		<COMMIT-F> refs/tmp/abc123456
	EOF
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "checksum not changed for not well-known refs" '
	git -C bare.git checksum >actual &&
	cat >expect<<-\EOF &&
		e5c68e5ed182b59a72ad65d6f84855ca
	EOF
	test_cmp expect actual &&
	git -C bare.git checksum -V
'

test_expect_success GIT_CHECKSUM "remove branch next" '
	(
		cd work &&
		git checkout main &&
		git push origin :refs/heads/next &&
		git push origin :refs/tmp/abc123456
	) &&
	git -C bare.git show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect<<-\EOF &&
		<COMMIT-F> refs/heads/main
		<COMMIT-F> refs/keep-around/577711d99f417fdc46fdbd13c1cc6361ed90283d
		<COMMIT-F> refs/remotes/origin/pu
	EOF
	test_cmp expect actual

'

test_expect_success GIT_CHECKSUM "verify checksum after remove branch" '
	cat >expect<<-\EOF &&
		a00dd5074d5493c2347986e6c40d2faf
	EOF
	git -C bare.git checksum >actual &&
	test_cmp expect actual &&
	git -C bare.git checksum -V
'

test_expect_success GIT_CHECKSUM "remove checksum" '
	rm "bare.git/$checksum" &&
	test_must_fail git -C bare.git checksum -V
'
test_expect_success GIT_CHECKSUM "recreate checksum" '
	test_path_is_missing "bare.git/$checksum" &&
	git -C bare.git checksum --init &&
	test_path_is_file "bare.git/$checksum" &&
	git -C bare.git checksum >actual &&
	cat >expect<<-\EOF &&
		a00dd5074d5493c2347986e6c40d2faf
	EOF
	test_cmp expect actual &&
	git -C bare.git checksum -V
'

test_done
