#!/bin/sh
# Copyright (c) 2006, Junio C Hamano.

test_description='Test fetching into packed-refs
'

GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main
export GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME
HOOK_OUTPUT=hook-output
checksum=info/checksum

. ./test-lib.sh

if type git-checksum
then
	test_set_prereq GIT_CHECKSUM
fi

test_commit_setvar () {
	amend=
	append=
	notick=
	signoff=
	indir=
	merge=
	tag=
	var=

	while test $# != 0
	do
		case "$1" in
		--merge)
			merge=t
			;;
		--tag)
			tag=t
			;;
		--amend)
			amend="--amend"
			;;
		--append)
			append=t
			;;
		--notick)
			notick=t
			;;
		--signoff)
			signoff="$1"
			;;
		-C)
			shift
			indir="$1"
			;;
		-*)
			echo >&2 "error: unknown option $1"
			return 1
			;;
		*)
			break
			;;
		esac
		shift
	done
	if test $# -lt 2
	then
		echo >&2 "error: test_commit_setvar must have at least 2 arguments"
		return 1
	fi
	var=$1
	shift
	indir=${indir:+"$indir"/}
	if test -z "$notick"
	then
		test_tick
	fi &&
	if test -n "$merge"
	then
		git ${indir:+ -C "$indir"} merge --no-edit --no-ff \
			${2:+-m "$2"} "$1" &&
		oid=$(git ${indir:+ -C "$indir"} rev-parse HEAD)
	elif test -n "$tag"
	then
		git ${indir:+ -C "$indir"} tag -m "$1" "$1" "${2:-HEAD}" &&
		oid=$(git ${indir:+ -C "$indir"} rev-parse "$1")
	else
		file=${2:-"$1.t"} &&
		if test -n "$append"
		then
			echo "${3-$1}" >>"$indir$file"
		else
			echo "${3-$1}" >"$indir$file"
		fi &&
		git ${indir:+ -C "$indir"} add "$file" &&
		git ${indir:+ -C "$indir"} commit $amend $signoff -m "$1" &&
		oid=$(git ${indir:+ -C "$indir"} rev-parse HEAD)
	fi &&
	eval $var=$oid
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
# without having to worry about future changes of the commit ID and spaces
# of the output.  Single quotes are replaced with double quotes, because
# it is boring to prepare unquoted single quotes in expect text.  We also
# remove some locale error messages, which break test if we turn on
# `GIT_TEST_GETTEXT_POISON=true` in order to test unintentional translations
# on plumbing commands.
make_user_friendly_and_stable_output () {
	_x40="$_x35$_x05"

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
		-e "s/$(get_abbrev_oid $J)[0-9a-f]*/<COMMIT-J>/g" \
		-e "s/$(get_abbrev_oid $K)[0-9a-f]*/<COMMIT-K>/g" \
		-e "s/$(get_abbrev_oid $TAG1)[0-9a-f]*/<TAG-1>/g" \
		-e "s/$(get_abbrev_oid $TAG2)[0-9a-f]*/<TAG-2>/g" \
		-e "s/$(get_abbrev_oid $TAG3)[0-9a-f]*/<TAG-3>/g" \
		-e "s/$(get_abbrev_oid $TAG4)[0-9a-f]*/<TAG-4>/g" \
		-e "s/$ZERO_OID/<ZERO-OID>/g" \
		-e "s/  *\$//" \
		-e "s/   */ /g" \
		-e "s/'/\"/g" \
		-e "s/	/    /g" \
		-e "s/$_x40[0-9a-f]*/<OID>/g" \
		-e "s/^index $_x05[0-9a-f]*\.\.$_x05[0-9a-f]*/index <OID1>..<OID2>/" \
		-e "s/$ZERO_OID/<ZERO-OID>/g"
}

test_loose_refs_count () {
	DIR="$1/refs" &&
	EXPECTED_COUNT="$2" &&
	test_path_is_dir "$DIR" &&
	find "$DIR" -type f >actual &&
	test_line_count = $EXPECTED_COUNT actual
}

test_cmp_packed_refs () {
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
	actual=${2:-actual-packed-refs} &&
	indir=${indir:+"$indir"/} &&
	test_path_is_file "$expect" &&
	test_when_finished "rm -f \"$actual\"" &&
	cat "${indir:-.}"/packed-refs |
		make_user_friendly_and_stable_output >"$actual" &&
	test_cmp "$expect" "$actual"
}

test_cmp_refs_txn_hook_output () {
	local indir= expect actual &&
	expect=${1:-expect} &&
	actual=${2:-actual-hook-output} &&
	indir=${indir:+"$indir"/} &&
	test_path_is_file "$expect" &&
	test_when_finished "rm -f \"$actual\"" &&
	cat "$HOOK_OUTPUT" |
		make_user_friendly_and_stable_output >"$actual" &&
	test_cmp "$expect" "$actual"
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

test_verify_checksum () {
	local indir= &&
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
	indir=${indir:+"$indir"/} &&
	test_path_is_file "${indir:-.}/$checksum" &&
	if ! git ${indir:+ -C "$indir"} checksum --verify
	then
		die "Mismatched git checksum"
	fi
}

clear_hook_output () {
	rm -f "$HOOK_OUTPUT"
}

remove_and_create_dest_repo () {
	rm -rf dest.git && git init --bare dest.git
}

###############################################################################

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

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
test_expect_success "setup worktree" '
	# Create commits in the main branch
	test_commit_setvar A "Commit-A" README.txt &&
	git branch topic/A &&
	git tag tag-A &&
	test_commit_setvar B "Commit-B" README.txt &&
	git branch topic/B &&
	git tag tag-B &&
	test_commit_setvar C "Commit-C" README.txt &&
	git branch topic/C &&
	git tag tag-C &&
	test_commit_setvar D "Commit-D" README.txt &&
	git branch topic/D &&
	git tag tag-D &&
	# Reset main branch to commit-C
	git reset --hard HEAD~ &&

	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_heads_and_tags expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
test_expect_success "prepare base.git" '
	git init --bare base.git &&
	git push base.git main topic/A topic/B topic/C tag-A tag-B tag-C &&
	git -C base.git update-ref refs/heads/topic/B $A &&
	test_loose_refs_count base.git 7 &&
	cat >expect <<-\EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C base.git expect
'

test_expect_success 'fetch as loose refs' '
	remove_and_create_dest_repo &&
	clear_hook_output &&
	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&

	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM "fetch as loose refs: check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "fetch as loose refs: check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_refs_txn_hook_output expect
'

test_expect_success "fetch to packed-refs (via args)" '
	remove_and_create_dest_repo &&
	clear_hook_output &&
	git -C dest.git \
		fetch --write-packed-refs ../base.git "+refs/*:refs/*" &&

	test_loose_refs_count dest.git 0 &&
	test_path_is_file dest.git/packed-refs &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect &&

	cat >expect <<-\EOF &&
		# pack-refs with: peeled fully-peeled sorted
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_packed_refs -C dest.git expect
'

test_expect_success GIT_CHECKSUM "fetch to packed-refs (via args): check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "fetch to packed-refs (via args): check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		<ZERO-OID> <COMMIT-C> HEAD
	EOF
	test_cmp_refs_txn_hook_output expect
'

test_expect_success 'fetch to packed-refs (via git config)' '
	remove_and_create_dest_repo &&
	clear_hook_output &&
	git -c fetch.writePackedRefs=true -C dest.git \
		fetch ../base.git "+refs/*:refs/*" &&

	test_loose_refs_count dest.git 0 &&
	test_path_is_file dest.git/packed-refs &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect &&

	cat >expect <<-\EOF &&
		# pack-refs with: peeled fully-peeled sorted
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_packed_refs -C dest.git expect
'

test_expect_success GIT_CHECKSUM "fetch to packed-refs (via config): check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "fetch to packed-refs (via config): check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		<ZERO-OID> <COMMIT-C> HEAD
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-C> refs/heads/main
		<ZERO-OID> <COMMIT-A> refs/heads/topic/A
		<ZERO-OID> <COMMIT-A> refs/heads/topic/B
		<ZERO-OID> <COMMIT-C> refs/heads/topic/C
		<ZERO-OID> <COMMIT-A> refs/tags/tag-A
		<ZERO-OID> <COMMIT-B> refs/tags/tag-B
		<ZERO-OID> <COMMIT-C> refs/tags/tag-C
		<ZERO-OID> <COMMIT-C> HEAD
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
test_expect_success 'incremental fetch new references' '
	git clone --mirror base.git source.git &&
	git push source.git topic/D tag-D &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&
	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -C dest.git fetch ../source.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&

	test_loose_refs_count dest.git 9 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM 'incremental fetch new references: check git-checksum' '
	test_verify_checksum -C dest.git
'

test_expect_success 'incremental fetch new references: check refs-txn hook' '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
test_expect_success 'incremental fetch new references (to packed-refs)' '
	git clone --mirror base.git source.git &&
	git push source.git topic/D tag-D &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&
	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -c fetch.writepackedrefs=true -C dest.git \
		fetch ../source.git "+refs/*:refs/*" &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-A> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_heads_and_tags -C dest.git expect &&

	test_loose_refs_count dest.git 7 &&

	cat >expect <<-EOF &&
		# pack-refs with: peeled fully-peeled sorted
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_packed_refs -C dest.git expect
'

test_expect_success GIT_CHECKSUM 'incremental fetch new references (to packed-refs): check git-checksum' '
	test_verify_checksum -C dest.git
'

test_expect_success 'incremental fetch new references (to packed-refs): check refs-txn hook' '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#
test_expect_success 'incremental fetch update references' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref refs/heads/topic/B $B &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&
	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -C dest.git fetch ../source.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&

	test_loose_refs_count dest.git 7 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM "incremental fetch update references: check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "incremental fetch update references: check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#
test_expect_success 'incremental fetch update references (to packed-refs)' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref refs/heads/topic/B $B &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&

	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -c fetch.writepackedrefs=true -C dest.git \
		fetch ../source.git "+refs/*:refs/*" &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect &&

	test_loose_refs_count dest.git 6 &&

	cat >expect <<-EOF &&
		# pack-refs with: peeled fully-peeled sorted
		<COMMIT-B> refs/heads/topic/B
	EOF
	test_cmp_packed_refs -C dest.git expect
'

test_expect_success GIT_CHECKSUM "incremental fetch: update references (to packed-refs): check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "incremental fetch: update references (to packed-refs): check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-B> refs/heads/topic/B
		## Call hook: reference-transaction prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/C (C, tag-C)
#
test_expect_success 'incremental fetch with --prune' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref -d refs/heads/topic/B &&
	git -C source.git update-ref -d refs/tags/tag-B &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&

	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -C dest.git fetch --prune ../source.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&

	test_loose_refs_count dest.git 5 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM "incremental fetch with --prune: check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "incremental fetch with --prune: check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic/B
		<COMMIT-B> <ZERO-OID> refs/tags/tag-B
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic/B
		<COMMIT-B> <ZERO-OID> refs/tags/tag-B
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/C (C, tag-C)
#
test_expect_success 'incremental fetch with --prune (to packed-refs)' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref -d refs/heads/topic/B &&
	git -C source.git update-ref -d refs/tags/tag-B &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&

	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -c fetch.writepackedrefs=true -C dest.git \
		fetch --prune ../source.git "+refs/*:refs/*" &&

	test_path_is_missing dest.git/packed-refs &&

	test_loose_refs_count dest.git 5 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-C> refs/heads/topic/C
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-C> refs/tags/tag-C
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM "incremental fetch with --prune (to packed-refs): check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "incremental fetch with --prune (to packed-refs): check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic/B
		<COMMIT-B> <ZERO-OID> refs/tags/tag-B
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <ZERO-OID> refs/heads/topic/B
		<COMMIT-B> <ZERO-OID> refs/tags/tag-B
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-A)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
test_expect_success 'incremental fetch with all kinds of updates' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref refs/heads/topic/B $B &&
	git -C source.git update-ref -d refs/heads/topic/C &&
	git -C source.git update-ref -d refs/tags/tag-C &&
	git push source.git topic/D tag-D &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&

	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -C dest.git fetch --prune ../source.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&

	test_loose_refs_count dest.git 7 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM "incremental with all kinds of updates: check git-checksum" '
	test_verify_checksum -C dest.git
'

test_expect_success "incremental with all kinds of updates: check refs-txn hook" '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic/C
		<COMMIT-C> <ZERO-OID> refs/tags/tag-C
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic/C
		<COMMIT-C> <ZERO-OID> refs/tags/tag-C
		## Call hook: reference-transaction prepared ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		## Call hook: reference-transaction committed ##
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction committed ##
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-A)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
test_expect_success 'incremental with all kinds of updates (to packed-refs)' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref refs/heads/topic/B $B &&
	git -C source.git update-ref -d refs/heads/topic/C &&
	git -C source.git update-ref -d refs/tags/tag-C &&
	git push source.git topic/D tag-D &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&

	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&

	clear_hook_output &&
	git -c fetch.writepackedrefs=true -C dest.git \
		fetch --prune ../source.git "+refs/*:refs/*" &&
	test_path_is_file dest.git/packed-refs &&

	cat >expect <<-EOF &&
		# pack-refs with: peeled fully-peeled sorted
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_packed_refs -C dest.git expect &&

	test_loose_refs_count dest.git 4 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM 'incremental with all kinds of updates (to packed-refs): check git-checksum' '
	test_verify_checksum -C dest.git
'

test_expect_success 'incremental with all kinds of updates (to packed-refs): check refs-txn hook' '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic/C
		<ZERO-OID> <ZERO-OID> refs/tags/tag-C
		<ZERO-OID> <COMMIT-B> refs/heads/topic/B
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction prepared ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic/C
		<COMMIT-C> <ZERO-OID> refs/tags/tag-C
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic/C
		<COMMIT-C> <ZERO-OID> refs/tags/tag-C
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_refs_txn_hook_output expect
'

# workdir:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
# base.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (A, tag-A)
#     topic/C (C, tag-C)
#
# source.git:
#
#   * main (C)
#     topic/A (A, tag-A)
#     topic/B (B, tag-B)
#     topic/C (C, tag-C)
#     topic/D (D, tag-D)
#
test_expect_success 'incremental fetch with old packed-refs (to packed-refs)' '
	git clone --mirror base.git source.git &&
	git -C source.git update-ref refs/heads/topic/B $B &&
	git -C source.git update-ref -d refs/heads/topic/C &&
	git -C source.git update-ref -d refs/tags/tag-C &&
	git push source.git topic/D tag-D &&
	test_when_finished "rm -rf source.git" &&

	remove_and_create_dest_repo &&

	git -C dest.git fetch ../base.git "+refs/*:refs/*" &&
	test_path_is_missing dest.git/packed-refs &&
	test_loose_refs_count dest.git 7 &&
	echo "$B refs/heads/topic/A"  >dest.git/packed-refs &&
	echo "$C refs/heads/topic/B" >>dest.git/packed-refs &&

	clear_hook_output &&
	git -c fetch.writepackedrefs=true -C dest.git \
		fetch --prune ../source.git "+refs/*:refs/*" &&
	test_path_is_file dest.git/packed-refs &&

	cat >expect <<-EOF &&
		# pack-refs with: peeled fully-peeled sorted
		<COMMIT-B> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_packed_refs -C dest.git expect &&

	test_loose_refs_count dest.git 4 &&
	cat >expect <<-EOF &&
		<COMMIT-C> refs/heads/main
		<COMMIT-A> refs/heads/topic/A
		<COMMIT-B> refs/heads/topic/B
		<COMMIT-D> refs/heads/topic/D
		<COMMIT-A> refs/tags/tag-A
		<COMMIT-B> refs/tags/tag-B
		<COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_heads_and_tags -C dest.git expect
'

test_expect_success GIT_CHECKSUM 'incremental fetch with old packed-refs (to packed-refs): check git-checksum' '
	test_verify_checksum -C dest.git
'

test_expect_success 'incremental fetch with old packed-refs (to packed-refs): check refs-txn hook' '
	cat >expect <<-\EOF &&
		## Call hook: reference-transaction prepared ##
		<ZERO-OID> <ZERO-OID> refs/heads/topic/C
		<ZERO-OID> <ZERO-OID> refs/tags/tag-C
		<ZERO-OID> <COMMIT-B> refs/heads/topic/B
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction prepared ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic/C
		<COMMIT-C> <ZERO-OID> refs/tags/tag-C
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
		## Call hook: reference-transaction committed ##
		<COMMIT-C> <ZERO-OID> refs/heads/topic/C
		<COMMIT-C> <ZERO-OID> refs/tags/tag-C
		<COMMIT-A> <COMMIT-B> refs/heads/topic/B
		<ZERO-OID> <COMMIT-D> refs/heads/topic/D
		<ZERO-OID> <COMMIT-D> refs/tags/tag-D
	EOF
	test_cmp_refs_txn_hook_output expect
'

test_done
