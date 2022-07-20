#!/bin/sh

test_description='reference transaction hooks'

GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main
export GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME

. ./test-lib.sh

test_expect_success setup '
	test_commit PRE &&
	PRE_OID=$(git rev-parse PRE) &&
	test_commit POST &&
	POST_OID=$(git rev-parse POST)
'

test_expect_success 'hook allows updating ref if successful' '
	git reset --hard PRE &&
	test_hook reference-transaction <<-\EOF &&
		echo "$*" >>actual
	EOF
	cat >expect <<-EOF &&
		prepared
		committed
	EOF
	git update-ref HEAD POST &&
	test_cmp expect actual
'

test_expect_success 'hook aborts updating ref in prepared state' '
	git reset --hard PRE &&
	test_hook reference-transaction <<-\EOF &&
		if test "$1" = prepared
		then
			exit 1
		fi
	EOF
	test_must_fail git update-ref HEAD POST 2>err &&
	test_i18ngrep "ref updates aborted by hook" err
'

test_expect_success 'hook gets all queued updates in prepared state' '
	test_when_finished "rm actual" &&
	git reset --hard PRE &&
	test_hook reference-transaction <<-\EOF &&
		if test "$1" = prepared
		then
			while read -r line
			do
				printf "%s\n" "$line"
			done >actual
		fi
	EOF
	cat >expect <<-EOF &&
		$PRE_OID $POST_OID HEAD
		$PRE_OID $POST_OID refs/heads/main
	EOF
	git update-ref HEAD POST <<-EOF &&
		update HEAD $ZERO_OID $POST_OID
		update refs/heads/main $ZERO_OID $POST_OID
	EOF
	test_cmp expect actual
'

test_expect_success 'hook gets all queued updates in committed state' '
	test_when_finished "rm actual" &&
	git reset --hard PRE &&
	test_hook reference-transaction <<-\EOF &&
		if test "$1" = committed
		then
			while read -r line
			do
				printf "%s\n" "$line"
			done >actual
		fi
	EOF
	cat >expect <<-EOF &&
		$PRE_OID $POST_OID HEAD
		$PRE_OID $POST_OID refs/heads/main
	EOF
	git update-ref HEAD POST &&
	test_cmp expect actual
'

test_expect_success 'hook gets all queued updates in aborted state' '
	test_when_finished "rm actual" &&
	git reset --hard PRE &&
	test_hook reference-transaction <<-\EOF &&
		if test "$1" = aborted
		then
			while read -r line
			do
				printf "%s\n" "$line"
			done >actual
		fi
	EOF
	cat >expect <<-EOF &&
		$ZERO_OID $POST_OID HEAD
		$ZERO_OID $POST_OID refs/heads/main
	EOF
	git update-ref --stdin <<-EOF &&
		start
		update HEAD POST $ZERO_OID
		update refs/heads/main POST $ZERO_OID
		abort
	EOF
	test_cmp expect actual
'

test_expect_success 'interleaving hook calls succeed' '
	test_when_finished "rm -r target-repo.git" &&

	git init --bare target-repo.git &&

	test_hook -C target-repo.git reference-transaction <<-\EOF &&
		echo $0 "$@" >>actual
	EOF

	test_hook -C target-repo.git update <<-\EOF &&
		echo $0 "$@" >>actual
	EOF

	cat >expect <<-EOF &&
		hooks/update refs/tags/PRE $ZERO_OID $PRE_OID
		hooks/reference-transaction prepared
		hooks/reference-transaction committed
		hooks/update refs/tags/POST $ZERO_OID $POST_OID
		hooks/reference-transaction prepared
		hooks/reference-transaction committed
	EOF

	git push ./target-repo.git PRE POST &&
	test_cmp expect target-repo.git/actual
'

HOOK_OUTPUT=hook-output

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

get_abbrev_oid () {
	local oid=$1 &&
	local suffix=${oid#???????} &&
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
	local indir= expect actual &&
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

test_expect_success 'setup git config and hook' '
	git config --global core.hooksPath "$HOME/test-hooks" &&
	git config --global core.abbrev 7 &&
	mkdir "test-hooks" &&
	write_script "test-hooks/reference-transaction" <<-EOF
		exec >>"$HOME/$HOOK_OUTPUT"
		printf "## Call hook: reference-transaction %9s ##\n" "\$@"
		while read -r line
		do
		    echo "\$line"
		done
	EOF
'

test_expect_success "setup base repository" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> HEAD
		<ZERO-OID> <COMMIT-A> refs/heads/main
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> HEAD
		<ZERO-OID> <COMMIT-A> refs/heads/main
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> HEAD
		<COMMIT-A> <COMMIT-B> refs/heads/main
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> HEAD
		<COMMIT-A> <COMMIT-B> refs/heads/main
		## Call hook: reference-transaction  prepared ##
		<COMMIT-B> <COMMIT-C> HEAD
		<COMMIT-B> <COMMIT-C> refs/heads/main
		## Call hook: reference-transaction committed ##
		<COMMIT-B> <COMMIT-C> HEAD
		<COMMIT-B> <COMMIT-C> refs/heads/main
	EOF

	git init base &&
	create_commits_in base A B C &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C base expect
'

test_expect_success "update-ref: setup workdir using git-clone" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/remotes/origin/main
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/remotes/origin/main
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> HEAD
		<ZERO-OID> <COMMIT-C> refs/heads/main
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> HEAD
		<ZERO-OID> <COMMIT-C> refs/heads/main
	EOF

	git clone base workdir &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref: create new refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic1
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic1
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic3
	EOF

	(
		cd workdir &&
		git update-ref refs/heads/topic1 $A &&
		git update-ref refs/heads/topic2 $A &&
		git update-ref refs/heads/topic3 $A
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref: update default branch" '
	test_when_finished "git switch main; rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic1
		<COMMIT-A> <COMMIT-B> HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic1
		<COMMIT-A> <COMMIT-B> HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-B> <COMMIT-A> refs/heads/topic1
		<COMMIT-B> <COMMIT-A> HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-B> <COMMIT-A> refs/heads/topic1
		<COMMIT-B> <COMMIT-A> HEAD
	EOF

	(
		cd workdir &&
		git switch topic1 &&
		git update-ref refs/heads/topic1 $B $A &&
		git update-ref refs/heads/topic1 $A
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref: update HEAD" '
	test_when_finished "git switch main; rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> HEAD
		<COMMIT-A> <COMMIT-B> refs/heads/topic1
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> HEAD
		<COMMIT-A> <COMMIT-B> refs/heads/topic1
		## Call hook: reference-transaction  prepared ##
		<COMMIT-B> <COMMIT-A> HEAD
		<COMMIT-B> <COMMIT-A> refs/heads/topic1
		## Call hook: reference-transaction committed ##
		<COMMIT-B> <COMMIT-A> HEAD
		<COMMIT-B> <COMMIT-A> refs/heads/topic1
	EOF

	(
		cd workdir &&
		git switch topic1 &&
		git update-ref HEAD $B $A &&
		git update-ref HEAD $A
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref: prepare packed_ref_store using pack-refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&
	git -C workdir pack-refs --all &&
	test_path_is_file workdir/.git/packed-refs &&
	test_path_is_missing $HOOK_OUTPUT
'

test_expect_success "update-ref: update refs already in packed_ref_store" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic2
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-C> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-C> refs/heads/topic3
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic4
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-C> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-C> refs/heads/topic4
	EOF

	(
		cd workdir &&
		git update-ref refs/heads/topic2 $B $A &&
		git update-ref refs/heads/topic3 $C &&
		git update-ref refs/heads/topic4 $A &&
		git update-ref refs/heads/topic4 $C
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
		<COMMIT-C> refs/heads/topic4
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref: remove refs with mixed ref_stores" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic1
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic1
		<COMMIT-A> <ZERO-OID> HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic1
		<COMMIT-A> <ZERO-OID> HEAD
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic2
		## Call hook: reference-transaction  prepared ##
		<COMMIT-B> <ZERO-OID> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<COMMIT-B> <ZERO-OID> refs/heads/topic2
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic3
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic3
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic4
	EOF

	(
		cd workdir &&
		git update-ref -d refs/heads/topic1 $A &&
		git update-ref -d refs/heads/topic2 $B &&
		git update-ref -d refs/heads/topic3 &&
		git update-ref -d refs/heads/topic4
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref --stdin: create new refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic1
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		<ZERO-OID> <COMMIT-A> refs/heads/topic3
		<ZERO-OID> <COMMIT-A> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic1
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		<ZERO-OID> <COMMIT-A> refs/heads/topic3
		<ZERO-OID> <COMMIT-A> HEAD
	EOF

	(
		cd workdir &&
		git update-ref --stdin <<-EOF
			create refs/heads/topic1 $A
			create refs/heads/topic2 $A
			create refs/heads/topic3 $A
		EOF
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
		<COMMIT-A> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref --stdin: prepare packed_ref_store using pack-refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&
	git -C workdir pack-refs --all
'

test_expect_success "update-ref --stdin: update refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic2
		<COMMIT-A> <COMMIT-C> refs/heads/topic3
		<ZERO-OID> <COMMIT-C> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic2
		<COMMIT-A> <COMMIT-C> refs/heads/topic3
		<ZERO-OID> <COMMIT-C> refs/heads/topic4
	EOF

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
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
		<COMMIT-C> refs/heads/topic4
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "update-ref --stdin: delete refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic1
		<ZERO-OID> <ZERO-OID> refs/heads/topic2
		<ZERO-OID> <ZERO-OID> refs/heads/topic3
		<ZERO-OID> <ZERO-OID> refs/heads/topic4
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic1
		<COMMIT-B> <ZERO-OID> refs/heads/topic2
		<COMMIT-C> <ZERO-OID> refs/heads/topic3
		<COMMIT-C> <ZERO-OID> refs/heads/topic4
		<COMMIT-A> <ZERO-OID> HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic1
		<COMMIT-B> <ZERO-OID> refs/heads/topic2
		<COMMIT-C> <ZERO-OID> refs/heads/topic3
		<COMMIT-C> <ZERO-OID> refs/heads/topic4
		<COMMIT-A> <ZERO-OID> HEAD
	EOF

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
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "branch: setup workdir using git-fetch" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/remotes/origin/main
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/remotes/origin/main
	EOF

	rm -rf workdir &&
	git init workdir &&
	git -C workdir remote add origin ../base &&
	git -C workdir fetch origin &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
	EOF

	rm $HOOK_OUTPUT &&
	git -C workdir switch -c main origin/main &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "branch: create new branches" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic1
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic1
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
	EOF

	(
		cd workdir &&
		git branch topic1 $A &&
		git branch topic2 $A
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-A> refs/heads/topic2
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "branch: prepare packed_ref_store using gc" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&
	git -C workdir gc &&
	test_path_is_file workdir/.git/packed-refs &&
	test_path_is_missing $HOOK_OUTPUT
'

test_expect_success "branch: update branch without old-oid" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic2
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic3
	EOF

	(
		cd workdir &&
		git branch -f topic2 $B &&
		git branch topic3 $C
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic1
		<COMMIT-B> refs/heads/topic2
		<COMMIT-C> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "branch: copy branches" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-B> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-B> refs/heads/topic4
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic5
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic5
	EOF

	(
		cd workdir &&
		git branch -c topic2 topic4 &&
		git branch -c topic3 topic5
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

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

test_expect_success "branch: rename branches" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-B> <ZERO-OID> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<COMMIT-B> <ZERO-OID> refs/heads/topic4
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-B> refs/heads/topic6
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-B> refs/heads/topic6
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic5
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic5
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic7
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic7
	EOF

	(
		cd workdir &&
		git branch -m topic4 topic6 &&
		git branch -m topic5 topic7
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

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

# Mismatched hook output for "git branch -d":
#
#  * The delete branches operation should be treated as one transaction,
#    but was splitted into several transactions on loose references,
#    and the "reference-transaction committed" command was executed
#    redundantly on the packed-ref-store.
#
# The differences are as follows:
#
#     @@ -2,11 +2,19 @@
#      <ZERO-OID> <ZERO-OID> refs/heads/topic1
#      <ZERO-OID> <ZERO-OID> refs/heads/topic2
#      <ZERO-OID> <ZERO-OID> refs/heads/topic3
#     +## Call hook: reference-transaction committed ##
#     +<ZERO-OID> <ZERO-OID> refs/heads/topic1
#     +<ZERO-OID> <ZERO-OID> refs/heads/topic2
#     +<ZERO-OID> <ZERO-OID> refs/heads/topic3
#     +## Call hook: reference-transaction  prepared ##
#     +<ZERO-OID> <ZERO-OID> refs/heads/topic1
#     +## Call hook: reference-transaction committed ##
#     +<ZERO-OID> <ZERO-OID> refs/heads/topic1
#      ## Call hook: reference-transaction  prepared ##
#     -<COMMIT-A> <ZERO-OID> refs/heads/topic1
#      <COMMIT-B> <ZERO-OID> refs/heads/topic2
#     -<COMMIT-C> <ZERO-OID> refs/heads/topic3
#      ## Call hook: reference-transaction committed ##
#     -<COMMIT-A> <ZERO-OID> refs/heads/topic1
#      <COMMIT-B> <ZERO-OID> refs/heads/topic2
#     +## Call hook: reference-transaction  prepared ##
#     +<COMMIT-C> <ZERO-OID> refs/heads/topic3
#     +## Call hook: reference-transaction committed ##
#      <COMMIT-C> <ZERO-OID> refs/heads/topic3
test_expect_failure "branch: remove branches" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic1
		<ZERO-OID> <ZERO-OID> refs/heads/topic2
		<ZERO-OID> <ZERO-OID> refs/heads/topic3
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic1
		<COMMIT-B> <ZERO-OID> refs/heads/topic2
		<COMMIT-C> <ZERO-OID> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic1
		<COMMIT-B> <ZERO-OID> refs/heads/topic2
		<COMMIT-C> <ZERO-OID> refs/heads/topic3
	EOF

	(
		cd workdir &&
		git branch -d topic1 topic2 topic3
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-B> refs/heads/topic6
		<COMMIT-C> refs/heads/topic7
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "tag: setup workdir using git-push" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
	EOF

	rm -rf workdir &&
	git init workdir &&
	git -C workdir config receive.denyCurrentBranch ignore &&
	git -C base push ../workdir "+refs/heads/*:refs/heads/*" &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect &&

	git -C workdir restore --staged -- . &&
	git -C workdir restore -- .
'

test_expect_success "tag: create new tags" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/tags/v1
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/tags/v1
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/tags/v2
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/tags/v2
	EOF

	(
		cd workdir &&
		git tag v1 $A &&
		git tag v2 $A
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/tags/v1
		<COMMIT-A> refs/tags/v2
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "tag: prepare packed_ref_store using pack-refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&
	git -C workdir pack-refs --all &&
	test_path_is_file workdir/.git/packed-refs &&
	test_path_is_missing $HOOK_OUTPUT
'

test_expect_success "tag: update refs to create loose refs" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-B> refs/tags/v2
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/tags/v2
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/tags/v3
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/tags/v3
	EOF

	(
		cd workdir &&
		git tag -f v2 $B &&
		git tag v3 $C
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/tags/v1
		<COMMIT-B> refs/tags/v2
		<COMMIT-C> refs/tags/v3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

# Mismatched hook output for "git tag -d":
#
#  * The delete tags operation should be treated as one transaction,
#    but was splitted into several transactions on loose references,
#    and the "reference-transaction committed" command was executed
#    redundantly on the packed-ref-store.
#
# The differences are as follows:
#
#     @@ -2,11 +2,19 @@
#      <ZERO-OID> <ZERO-OID> refs/tags/v1
#      <ZERO-OID> <ZERO-OID> refs/tags/v2
#      <ZERO-OID> <ZERO-OID> refs/tags/v3
#     +## Call hook: reference-transaction committed ##
#     +<ZERO-OID> <ZERO-OID> refs/tags/v1
#     +<ZERO-OID> <ZERO-OID> refs/tags/v2
#     +<ZERO-OID> <ZERO-OID> refs/tags/v3
#     +## Call hook: reference-transaction  prepared ##
#     +<ZERO-OID> <ZERO-OID> refs/tags/v1
#     +## Call hook: reference-transaction committed ##
#     +<ZERO-OID> <ZERO-OID> refs/tags/v1
#      ## Call hook: reference-transaction  prepared ##
#     -<COMMIT-A> <ZERO-OID> refs/tags/v1
#      <COMMIT-B> <ZERO-OID> refs/tags/v2
#     -<COMMIT-C> <ZERO-OID> refs/tags/v3
#      ## Call hook: reference-transaction committed ##
#     -<COMMIT-A> <ZERO-OID> refs/tags/v1
#      <COMMIT-B> <ZERO-OID> refs/tags/v2
#     +## Call hook: reference-transaction  prepared ##
#     +<COMMIT-C> <ZERO-OID> refs/tags/v3
#     +## Call hook: reference-transaction committed ##
#      <COMMIT-C> <ZERO-OID> refs/tags/v3
test_expect_failure "tag: remove tags with mixed ref_stores" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> refs/tags/v1
		<ZERO-OID> <ZERO-OID> refs/tags/v2
		<ZERO-OID> <ZERO-OID> refs/tags/v3
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <ZERO-OID> refs/tags/v1
		<COMMIT-B> <ZERO-OID> refs/tags/v2
		<COMMIT-C> <ZERO-OID> refs/tags/v3
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <ZERO-OID> refs/tags/v1
		<COMMIT-B> <ZERO-OID> refs/tags/v2
		<COMMIT-C> <ZERO-OID> refs/tags/v3
	EOF

	(
		cd workdir &&
		git tag -d v1 v2 v3
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "worktree: setup workdir using push --atomic" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
	EOF

	rm -rf workdir &&
	git init --bare repo.git &&
	git -C base push --atomic --mirror ../repo.git &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&
	rm $HOOK_OUTPUT &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/remotes/origin/main
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/remotes/origin/main
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> HEAD
		<ZERO-OID> <COMMIT-C> refs/heads/main
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> HEAD
		<ZERO-OID> <COMMIT-C> refs/heads/main
	EOF

	git clone --no-local repo.git workdir &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "worktree: topic1: commit --amend" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic1
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic1
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <COMMIT-D> HEAD
		<COMMIT-C> <COMMIT-D> refs/heads/topic1
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <COMMIT-D> HEAD
		<COMMIT-C> <COMMIT-D> refs/heads/topic1
	EOF

	(
		cd workdir &&
		git checkout -b topic1 &&
		git commit --amend -m "C (amend)"
	) &&
	D=$(git -C workdir rev-parse HEAD) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "worktree: topic2: merge" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic2
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> ORIG_HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> ORIG_HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-E> HEAD
		<COMMIT-A> <COMMIT-E> refs/heads/topic2
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-E> HEAD
		<COMMIT-A> <COMMIT-E> refs/heads/topic2
	EOF

	(
		cd workdir &&
		git checkout -b topic2 $A &&
		git merge --no-ff main &&
		test_path_is_file B.t &&
		test_path_is_file C.t
	) &&
	E=$(git -C workdir rev-parse HEAD) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "worktree: topic3: cherry-pick" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic3
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> CHERRY_PICK_HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> CHERRY_PICK_HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-F> HEAD
		<COMMIT-A> <COMMIT-F> refs/heads/topic3
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-F> HEAD
		<COMMIT-A> <COMMIT-F> refs/heads/topic3
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <ZERO-OID> CHERRY_PICK_HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> CHERRY_PICK_HEAD
	EOF

	(
		cd workdir &&
		git checkout -b topic3 $A &&
		git cherry-pick $C &&
		test_path_is_file C.t &&
		test_path_is_missing B.t
	) &&
	F=$(git -C workdir rev-parse HEAD) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
		<COMMIT-F> refs/heads/topic3
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "worktree: topic4: rebase" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<COMMIT-A> <COMMIT-G> ORIG_HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-G> ORIG_HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-G> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-G> <COMMIT-C> HEAD
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> REBASE_HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <ZERO-OID> REBASE_HEAD
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-G> CHERRY_PICK_HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-G> CHERRY_PICK_HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <COMMIT-H> HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <COMMIT-H> HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-G> <ZERO-OID> CHERRY_PICK_HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-G> <ZERO-OID> CHERRY_PICK_HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-G> <COMMIT-H> refs/heads/topic4
		## Call hook: reference-transaction committed ##
		<COMMIT-G> <COMMIT-H> refs/heads/topic4
	EOF

	git -C workdir checkout -b topic4 $A &&
	create_commits_in workdir G &&
	rm $HOOK_OUTPUT &&
	git -C workdir rebase main &&
	H=$(git -C workdir rev-parse HEAD) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-D> refs/heads/topic1
		<COMMIT-E> refs/heads/topic2
		<COMMIT-F> refs/heads/topic3
		<COMMIT-H> refs/heads/topic4
	EOF
	test_cmp_heads_and_tags -C workdir expect
'

test_expect_success "worktree: topic5: revert" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic5
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic5
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <COMMIT-I> HEAD
		<COMMIT-C> <COMMIT-I> refs/heads/topic5
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <COMMIT-I> HEAD
		<COMMIT-C> <COMMIT-I> refs/heads/topic5
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <ZERO-OID> CHERRY_PICK_HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <ZERO-OID> CHERRY_PICK_HEAD
	EOF

	(
		cd workdir &&
		git checkout -b topic5 $C &&
		git revert HEAD &&
		test_path_is_file B.t &&
		test_path_is_missing C.t
	) &&
	I=$(git -C workdir rev-parse HEAD) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

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

test_expect_success "worktree: topic6: reset" '
	test_when_finished "rm -f $HOOK_OUTPUT" &&

	cat >expect <<-\EOF &&
		## Call hook: reference-transaction  prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic6
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic6
		## Call hook: reference-transaction  prepared ##
		<COMMIT-G> <COMMIT-C> ORIG_HEAD
		## Call hook: reference-transaction committed ##
		<COMMIT-G> <COMMIT-C> ORIG_HEAD
		## Call hook: reference-transaction  prepared ##
		<COMMIT-C> <COMMIT-B> HEAD
		<COMMIT-C> <COMMIT-B> refs/heads/topic6
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <COMMIT-B> HEAD
		<COMMIT-C> <COMMIT-B> refs/heads/topic6
	EOF

	(
		cd workdir &&
		git checkout -b topic6 $C &&
		git reset --hard $B
	) &&
	make_user_friendly_and_stable_output <$HOOK_OUTPUT >actual &&
	test_cmp expect actual &&

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
