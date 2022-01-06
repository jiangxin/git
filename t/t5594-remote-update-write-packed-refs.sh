#!/bin/sh
# Copyright (c) 2006, Junio C Hamano.

test_description='Test fetching into packed-refs
'

GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME=main
export GIT_TEST_DEFAULT_INITIAL_BRANCH_NAME
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
		-e "s/  *\$//" \
		-e "s/   */ /g" \
		-e "s/'/\"/g" \
		-e "s/	/    /g" \
		-e "s/$_x40[0-9a-f]*/<OID>/g" \
		-e "s/^index $_x05[0-9a-f]*\.\.$_x05[0-9a-f]*/index <OID1>..<OID2>/" \
		-e "s/$ZERO_OID/<ZERO-OID>/g"
}

assert_no_loose () {
	test_loose_refs_count dest.git 0
}

test_loose_refs_count () {
	DIR="$1/refs" &&
	EXPECTED_COUNT="$2" &&
	test_path_is_dir "$DIR" &&
	find "$DIR" -type f >actual &&
	test_line_count = $EXPECTED_COUNT actual
}

test_loose_refs_count () {
	DIR="$1/refs" &&
	EXPECTED_COUNT="$2" &&
	test_path_is_dir "$DIR" &&
	find "$DIR" -type f >actual &&
	test_line_count = $EXPECTED_COUNT actual
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


###############################################################################

# workdir:
#
#   * main (C)
#     branch-A (A, tag-A)
#     branch-B (B, tag-B)
#     branch-C (C, tag-C)
#
test_expect_success setup '
	test_commit_setvar A "Commit-A" README.txt &&
	git branch branch-A &&
	git tag tag-A &&
	test_commit_setvar B "Commit-B" README.txt &&
	git branch branch-B &&
	git tag tag-B &&
	test_commit_setvar C "Commit-C" README.txt &&
	git branch branch-C &&
	git tag tag-C &&
	git init --bare dest.git &&
	git -C dest.git remote add origin --mirror=fetch "file://$TRASH_DIRECTORY"
'
# workdir:
#
#   * main (C)
#     branch-A (A, tag-A)
#     branch-B (B, tag-B)
#     branch-C (C, tag-C)
#
test_expect_success 'fetch as loose refs' '
	git -C dest.git \
		-c fetch.writePackedRefs=false \
		remote update &&
	test_path_is_missing dest.git/packed-refs &&
	cat >expect <<-EOF &&
	<COMMIT-C> HEAD
	<COMMIT-A> refs/heads/branch-A
	<COMMIT-B> refs/heads/branch-B
	<COMMIT-C> refs/heads/branch-C
	<COMMIT-C> refs/heads/main
	<COMMIT-A> refs/tags/tag-A
	<COMMIT-B> refs/tags/tag-B
	<COMMIT-C> refs/tags/tag-C
	EOF
	git -C dest.git show-ref --head |
		make_user_friendly_and_stable_output >actual &&
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "fetch as loose refs: check git-checksum" '
	test_verify_checksum -C dest.git
'

# workdir:
#
#     branch-A (A, tag-A)
#                  tag-B
#                  tag-C
#   * branch-C (D)
#
# dest (loose):
#   * main (C)
#     branch-A (A, tag-A)
#     branch-B (B, tag-B)
#     branch-C (C, tag-C)
#
# dest (packed-refs):
#     branch-A (B) # no effect
#
test_expect_success 'delete branch-B and change branch-C' '
	# updates on worktree
	git branch -D branch-B &&
	test_commit_setvar D "Commit-D" README.txt &&
	git branch -M branch-C &&

	# packed-refs will be override by loose refs
	echo "$B refs/heads/branch-A" >dest.git/packed-refs
'

test_expect_success 'remote update --write-packed-refs' '
	git -C dest.git \
		-c pack.refStoreThreshold=1 \
		remote update --write-packed-refs --prune &&

	test_loose_refs_count dest.git 4 &&
	cat >expect <<-EOF &&
	# pack-refs with: peeled fully-peeled sorted
	<COMMIT-B> refs/heads/branch-A
	<COMMIT-D> refs/heads/branch-C
	EOF
	cat dest.git/packed-refs |
		make_user_friendly_and_stable_output >actual &&
	test_cmp expect actual &&

	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/branch-A
	<COMMIT-D> refs/heads/branch-C
	<COMMIT-A> refs/tags/tag-A
	<COMMIT-B> refs/tags/tag-B
	<COMMIT-C> refs/tags/tag-C
	EOF
	git -C dest.git show-ref --head |
		make_user_friendly_and_stable_output >actual &&
	test_cmp expect actual
'

test_expect_success GIT_CHECKSUM "remote update --write-packed-refs: check git-checksum" '
	test_verify_checksum -C dest.git
'

test_done
