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

test_expect_success GIT_CHECKSUM "create initial checksum file with -c init.checksum=true" '
	git -c init.checksum=true init --bare init-1.git &&
	test_path_is_file init-1.git/info/checksum
'

test_expect_success GIT_CHECKSUM "no initial checksum file with -c init.checksum=false" '
	git -c init.checksum=false init --bare init-2.git &&
	test_path_is_missing init-2.git/info/checksum
'

test_expect_success GIT_CHECKSUM "init with default init.checksum=true" '
	git init --bare init-3.git &&
	test_path_is_file init-3.git/info/checksum
'

test_expect_success GIT_CHECKSUM "create an empty checksum before commit" '
	test_when_finished "rm -rf bare.git" &&
	if ! test -z "$test_tick"
	then
		unset test_tick
	fi &&
	create_bare_repo bare.git &&
	test_path_is_file bare.git/$checksum &&
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
	test_path_is_file "bare.git/$checksum" &&
	rm "bare.git/$checksum" &&
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

## The following testcases are copied from t1416.

test_expect_success GIT_CHECKSUM "setup git config and test_tick" '
	git config --global core.abbrev 7 &&
	if ! test -z "$test_tick"
	then
		unset test_tick
	fi
'

test_expect_success GIT_CHECKSUM "setup base repository" '
	git init base &&
	create_commits_in base A B C &&
	git -C base checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C base expect
'

test_expect_success GIT_CHECKSUM "update-ref: setup workdir using git-clone" '
	git clone base workdir &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref: create new refs" '
	(
		cd workdir &&
		git update-ref refs/heads/topic1 $A &&
		git update-ref refs/heads/topic2 $A &&
		git update-ref refs/heads/topic3 $A
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref: update HEAD, a symbolic-ref" '
	test_when_finished "git -C workdir switch main" &&
	(
		cd workdir &&
		git switch topic1 &&
		git update-ref HEAD $B $A &&
		git update-ref HEAD $A &&
		git switch main
	) &&
	git -C workdir checksum --verify &&
	git -C workdir checksum >actual &&
	cat >expect <<-\EOF &&
		62d089191391ac5bbbda866ff3e0ca10
	EOF
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref: call git-pack-refs to create packed_ref_store" '
	git -C workdir pack-refs --all &&
	git -C workdir checksum --verify &&
	git -C workdir checksum >actual &&
	cat >expect <<-\EOF &&
		62d089191391ac5bbbda866ff3e0ca10
	EOF
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "update-ref: update refs already packed to .git/packed-refs" '
	(
		cd workdir &&
		git update-ref refs/heads/topic2 $B $A &&
		git update-ref refs/heads/topic3 $C &&
		git update-ref refs/heads/topic4 $A &&
		git update-ref refs/heads/topic4 $C
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
		<COMMIT-C> refs/heads/topic4
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref: remove refs with mixed ref_stores" '
	(
		cd workdir &&
		git update-ref -d refs/heads/topic1 $A &&
		git update-ref -d refs/heads/topic2 $B &&
		git update-ref -d refs/heads/topic3 &&
		git update-ref -d refs/heads/topic4
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref --stdin: create new refs" '
	test_when_finished "git -C workdir pack-refs --all" &&

	(
		cd workdir &&
		git update-ref --stdin <<-EOF
			create refs/heads/topic1 $A
			create refs/heads/topic2 $A
			create refs/heads/topic3 $A
		EOF
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref --stdin: update refs" '
	(
		cd workdir &&
		git update-ref --stdin <<-EOF
			start
			update refs/heads/topic2 $B $A
			update refs/heads/topic3 $C
			create refs/heads/topic4 $C
			prepare
			commit
		EOF
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
		<COMMIT-C> refs/heads/topic4
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "update-ref --stdin: delete refs" '
	(
		cd workdir &&
		git update-ref --stdin <<-EOF
			start
			delete refs/heads/topic1
			delete refs/heads/topic2 $B
			delete refs/heads/topic3
			delete refs/heads/topic4
			prepare
			commit
		EOF
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "branch: setup workdir using git-fetch" '
	rm -rf workdir &&
	git init workdir &&
	git -C workdir remote add origin ../base &&
	git -C workdir fetch origin &&
	git -C workdir checksum --verify &&

	git -C workdir switch -c main origin/main &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "branch: create new branches" '
	(
		cd workdir &&
		git branch topic1 $A &&
		git branch topic2 $A
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "branch: call git-gc to create packed_ref_store" '
	git -C workdir gc &&
	test_path_is_file workdir/.git/packed-refs &&
	git -C workdir checksum --verify
'

test_expect_success GIT_CHECKSUM "branch: update refs to create loose refs" '
	(
		cd workdir &&
		git branch -f topic2 $B &&
		git branch topic3 $C
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "branch: copy branches" '
	(
		cd workdir &&
		git branch -c topic2 topic4 &&
		git branch -c topic3 topic5
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
		<COMMIT-B> refs/heads/topic4
		<COMMIT-C> refs/heads/topic5
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "branch: rename branches" '
	(
		cd workdir &&
		git branch -m topic4 topic6 &&
		git branch -m topic5 topic7
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
		<COMMIT-B> refs/heads/topic6
		<COMMIT-C> refs/heads/topic7
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "branch: remove branches" '
	(
		cd workdir &&
		git branch -d topic1 topic2 topic3
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-B> refs/heads/topic6
		<COMMIT-C> refs/heads/topic7
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "tag: setup workdir using git-push" '
	rm -rf workdir &&
	git init workdir &&
	git -C workdir config receive.denyCurrentBranch ignore &&
	git -C base push ../workdir "+refs/heads/*:refs/heads/*" &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect &&

	git -C workdir restore --staged -- . &&
	git -C workdir restore -- .
'

test_expect_success GIT_CHECKSUM "tag: create new tags" '
	(
		cd workdir &&
		git tag v1 $A &&
		git tag v2 $A
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/tags/v1
		<COMMIT-A> refs/tags/v2
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "tag: call git-pack-refs to create packed_ref_store" '
	git -C workdir pack-refs --all &&
	test_path_is_file workdir/.git/packed-refs &&
	git -C workdir checksum --verify
'

test_expect_success GIT_CHECKSUM "tag: update refs to create loose refs" '
	(
		cd workdir &&
		git tag -f v2 $B &&
		git tag v3 $C
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/tags/v1
		<COMMIT-B> refs/tags/v2
		<COMMIT-C> refs/tags/v3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "tag: remove tags with mixed ref_stores" '
	(
		cd workdir &&
		git tag -d v1 &&
		git tag -d v2 &&
		git tag -d v3
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: setup workdir using push --atomic" '
	rm -rf workdir &&
	git init --bare repo.git &&
	git -C base push --atomic --mirror ../repo.git &&
	git -C repo.git checksum --verify &&

	git clone --no-local repo.git workdir &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: topic1: commit --amend" '
	(
		cd workdir &&
		git checkout -b topic1 &&
		git commit --amend -m "C (amend)"
	) &&
	D=$(git -C workdir rev-parse HEAD) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: topic2: merge" '
	(
		cd workdir &&
		git checkout -b topic2 $A &&
		git merge --no-ff main &&
		test_path_is_file B.t &&
		test_path_is_file C.t
	) &&
	E=$(git -C workdir rev-parse HEAD) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: topic3: cherry-pick" '
	(
		cd workdir &&
		git checkout -b topic3 $A &&
		git cherry-pick $C &&
		test_path_is_file C.t &&
		test_path_is_missing B.t
	) &&
	F=$(git -C workdir rev-parse HEAD) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
		<COMMIT-F> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: topic4: rebase" '
	git -C workdir checkout -b topic4 $A &&
	create_commits_in workdir G &&
	git -C workdir rebase main &&
	H=$(git -C workdir rev-parse HEAD) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
		<COMMIT-F> refs/heads/topic3
		<COMMIT-H> refs/heads/topic4
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: topic5: revert" '
	(
		cd workdir &&
		git checkout -b topic5 $C &&
		git revert HEAD &&
		test_path_is_file B.t &&
		test_path_is_missing C.t
	) &&
	I=$(git -C workdir rev-parse HEAD) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
		<COMMIT-F> refs/heads/topic3
		<COMMIT-H> refs/heads/topic4
		<COMMIT-I> refs/heads/topic5
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success GIT_CHECKSUM "worktree: topic6: reset" '
	(
		cd workdir &&
		git checkout -b topic6 $C &&
		git reset --hard $B
	) &&
	git -C workdir checksum --verify &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
		<COMMIT-F> refs/heads/topic3
		<COMMIT-H> refs/heads/topic4
		<COMMIT-I> refs/heads/topic5
		<COMMIT-B> refs/heads/topic6
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_done
