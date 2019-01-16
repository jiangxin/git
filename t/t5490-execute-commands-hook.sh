#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='Test git update-ref and basic ref logging'
. ./test-lib.sh

Z=$_z40

m=refs/heads/master
n_dir=refs/heads/gu
n=$n_dir/fixes
outside=refs/foo
bare=bare-repo
work=workdir

create_test_commits ()
{
	prfx="$1"
	for name in A B C D E F
	do
		test_tick &&
		T=$(git write-tree) &&
		sha1=$(echo $name | git commit-tree $T) &&
		eval $prfx$name=$sha1
	done
}

test_expect_success setup '
	git init --bare $bare &&
	git clone --no-local $bare $work &&
	git --git-dir=$bare config --add receive.executeCommandsRefs refs/for/ &&
	git --git-dir=$bare config --add receive.executeCommandsRefs refs/drafts &&
	cd $work &&
	create_test_commits ""
'

cat >"$TRASH_DIRECTORY/$bare/hooks/execute-commands" <<EOF
#!/bin/sh

printf >&2 "execute: execute-commands\n"

if test "\$1" = "--pre-receive"
then
	printf >&2 ">> pre-receive mode\n"
fi

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done
EOF

cat >"$TRASH_DIRECTORY/$bare/hooks/pre-receive" <<EOF
#!/bin/sh

printf >&2 "execute: pre-receive hook\n"

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done
EOF

cat >"$TRASH_DIRECTORY/$bare/hooks/post-receive" <<EOF
#!/bin/sh

printf >&2 "execute: post-receive hook\n"

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done
EOF

chmod a+x \
	"$TRASH_DIRECTORY/$bare/hooks/pre-receive" \
	"$TRASH_DIRECTORY/$bare/hooks/post-receive" \
	"$TRASH_DIRECTORY/$bare/hooks/execute-commands"

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: pre-receive hook
remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/master.
remote: execute: post-receive hook
remote: >> old: 0000000000000000000000000000000000000000, new: 102939797ab91a4f201d131418d2c9d919dcdd2c, ref: refs/heads/master.
EOF

test_expect_success "push to create master" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $A &&
	git push origin HEAD:$m 2>&1 | grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> pre-receive mode
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: execute: execute-commands
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: execute: post-receive hook
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
EOF

test_expect_success "push to special reference" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $B &&
	git push origin HEAD:refs/for/master/my/topic 2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> pre-receive mode
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/drafts/master/my/topic.
remote: execute: execute-commands
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/drafts/master/my/topic.
remote: execute: post-receive hook
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/drafts/master/my/topic.
EOF

test_expect_success "push to special reference" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $B &&
	git push origin HEAD:refs/drafts/master/my/topic 2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> pre-receive mode
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/drafts/master/my/topic.
remote: execute: execute-commands
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/drafts/master/my/topic.
remote: execute: post-receive hook
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/drafts/master/my/topic.
EOF


test_expect_success "push to multiple special references" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $B &&
	git push origin \
		HEAD:refs/for/master/my/topic \
		HEAD:refs/drafts/master/my/topic \
		2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> pre-receive mode
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: execute: pre-receive hook
remote: >> old: 102939797ab91a4f201d131418d2c9d919dcdd2c, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/heads/master.
remote: execute: execute-commands
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
remote: execute: post-receive hook
remote: >> old: 102939797ab91a4f201d131418d2c9d919dcdd2c, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/heads/master.
remote: >> old: 0000000000000000000000000000000000000000, new: 56d5c1374e8028a1e122ab046ab7b98165342dc4, ref: refs/for/master/my/topic.
EOF

test_expect_success "push to mixed references" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $B &&
	git push -f origin \
		HEAD:refs/for/master/my/topic \
		HEAD:refs/heads/master \
		2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/$bare/hooks/execute-commands" <<EOF
#!/bin/sh

printf >&2 "execute: execute-commands\n"

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done

if test "\$1" = "--pre-receive"
then
	printf >&2 ">> ERROR: auth failed in pre-receive mode\n"
	exit 1
fi
EOF

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> old: 0000000000000000000000000000000000000000, new: 3cceb89b690679aecbe1db39079f99221f1aaaa6, ref: refs/for/master/my/topic.
remote: >> ERROR: auth failed in pre-receive mode
EOF

test_expect_success "push to mixed references (auth failed in execute-commands)" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $C &&
	git push -f origin \
		HEAD:refs/for/master/my/topic \
		HEAD:refs/heads/master \
		2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/$bare/hooks/execute-commands" <<EOF
#!/bin/sh

printf >&2 "execute: execute-commands\n"

if test "\$1" = "--pre-receive"
then
	printf >&2 ">> in pre-receive mode\n"
fi

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done

EOF

cat >"$TRASH_DIRECTORY/$bare/hooks/pre-receive" <<EOF
#!/bin/sh

printf >&2 "execute: pre-receive hook\n"

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done

printf >&2 ">> ERROR: auth failed in pre-receive hook\n"
exit 1
EOF


cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> in pre-receive mode
remote: >> old: 0000000000000000000000000000000000000000, new: 26caa67a0d551891a2ecec76098a9f8e705ab059, ref: refs/for/master/my/topic.
remote: execute: pre-receive hook
remote: >> old: 56d5c1374e8028a1e122ab046ab7b98165342dc4, new: 26caa67a0d551891a2ecec76098a9f8e705ab059, ref: refs/heads/master.
remote: >> ERROR: auth failed in pre-receive hook
EOF

test_expect_success "push to mixed references (auth failed in execute-commands)" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $D &&
	git push -f origin \
		HEAD:refs/for/master/my/topic \
		HEAD:refs/heads/master \
		2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

cat >"$TRASH_DIRECTORY/$bare/hooks/execute-commands" <<EOF
#!/bin/sh

printf >&2 "execute: execute-commands\n"

if test "\$1" = "--pre-receive"
then
	printf >&2 ">> in pre-receive mode\n"
fi

while read old new ref
do
	printf >&2 ">> old: \$old, new: \$new, ref: \$ref.\n"
done

if test -n "\$GIT_VAR1"
then
	printf >&2 ">> has env: GIT_VAR1=\$GIT_VAR1.\n"
fi

if test -n "\$GIT_VAR2"
then
	printf >&2 ">> has env: GIT_VAR2=\$GIT_VAR2.\n"
fi

if test -n "\$AGIT_VAR1"
then
	printf >&2 ">> has env: AGIT_VAR1=\$AGIT_VAR1.\n"
fi

if test -n "\$AGIT_VAR2"
then
	printf >&2 ">> has env: AGIT_VAR2=\$AGIT_VAR2.\n"
fi

printf "GIT_VAR1=foo\n"
printf "GIT_VAR2=bar\n"
printf "AGIT_VAR1=foo\n"
printf "AGIT_VAR2=bar\n"
EOF

cat >"$TRASH_DIRECTORY/expected" <<EOF
remote: execute: execute-commands
remote: >> in pre-receive mode
remote: >> old: 0000000000000000000000000000000000000000, new: 26caa67a0d551891a2ecec76098a9f8e705ab059, ref: refs/for/master/my/topic.
remote: execute: execute-commands
remote: >> old: 0000000000000000000000000000000000000000, new: 26caa67a0d551891a2ecec76098a9f8e705ab059, ref: refs/for/master/my/topic.
remote: >> has env: AGIT_VAR1=foo.
remote: >> has env: AGIT_VAR2=bar.
remote: execute: post-receive hook
remote: >> old: 0000000000000000000000000000000000000000, new: 26caa67a0d551891a2ecec76098a9f8e705ab059, ref: refs/for/master/my/topic.
EOF

test_expect_success "push to mixed references (auth failed in execute-commands)" '
	cd "$TRASH_DIRECTORY/$work" &&
	git update-ref HEAD $D &&
	git push -f origin \
		HEAD:refs/for/master/my/topic \
		2>&1 | \
		grep "^remote:" | sed -e "s/ \+$//g" >actual &&
	test_cmp "$TRASH_DIRECTORY/expected" actual
'

test_done
