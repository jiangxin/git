#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='git pack-redundant test'

. ./test-lib.sh

create_commits () {
	parent=
	for name in A B C D E F G H I J K L M N O P Q R
	do
		test_tick &&
		T=$(git write-tree) &&
		if test -z "$parent"
		then
			oid=$(echo $name | git commit-tree $T)
		else
			oid=$(echo $name | git commit-tree -p $parent $T)
		fi &&
		eval $name=$oid &&
		parent=$oid ||
		return 1
	done
	git update-ref refs/heads/master $R
}

create_pack_1 () {
	P1=$(git -C objects/pack pack-objects -q pack <<-EOF
		$T
		$A
		$B
		$C
		$D
		$E
		$F
		$R
		EOF
	) &&
	eval P$P1=P1:$P1
}

create_pack_2 () {
	P2=$(git -C objects/pack pack-objects -q pack <<-EOF
		$B
		$C
		$D
		$E
		$G
		$H
		$I
		EOF
	) &&
	eval P$P2=P2:$P2
}

create_pack_3 () {
	P3=$(git -C objects/pack pack-objects -q pack <<-EOF
		$F
		$I
		$J
		$K
		$L
		$M
		EOF
	) &&
	eval P$P3=P3:$P3
}

create_pack_4 () {
	P4=$(git -C objects/pack pack-objects -q pack <<-EOF
		$J
		$K
		$L
		$M
		$P
		EOF
	) &&
	eval P$P4=P4:$P4
}

create_pack_5 () {
	P5=$(git -C objects/pack pack-objects -q pack <<-EOF
		$G
		$H
		$N
		$O
		EOF
	) &&
	eval P$P5=P5:$P5
}

create_pack_6 () {
	P6=$(git -C objects/pack pack-objects -q pack <<-EOF
		$N
		$O
		$Q
		EOF
	) &&
	eval P$P6=P6:$P6
}

create_pack_7 () {
	P7=$(git -C objects/pack pack-objects -q pack <<-EOF
		$P
		$Q
		EOF
	) &&
	eval P$P7=P7:$P7
}

create_pack_8 () {
	P8=$(git -C objects/pack pack-objects -q pack <<-EOF
		$A
		EOF
	) &&
	eval P$P8=P8:$P8
}

format_packfiles () {
	sed \
		-e "s#.*/pack-\(.*\)\.idx#\1#" \
		-e "s#.*/pack-\(.*\)\.pack#\1#" |
	sort -u |
	while read p
	do
		if test -z "$(eval echo \${P$p})"
		then
			echo $p
		else
			eval echo "\${P$p}"
		fi
	done |
	sort
}

test_expect_success 'setup master.git' '
	git init --bare master.git &&
	cd master.git &&
	create_commits
'

test_expect_success 'no redundant for pack 1, 2, 3' '
	create_pack_1 && create_pack_2 && create_pack_3 &&
	git pack-redundant --all >out &&
	test_must_be_empty out
'

test_expect_success 'create pack 4, 5' '
	create_pack_4 && create_pack_5
'

cat >expected <<EOF
P3:$P3
EOF

test_expect_success 'one of pack-2/pack-3 is redundant' '
	git pack-redundant --all >out &&
	format_packfiles <out >actual &&
	test_cmp expected actual
'

test_expect_success 'create pack 6, 7' '
	create_pack_6 && create_pack_7
'

# Only after calling create_pack_6, we can use $P6 variable.
cat >expected <<EOF
P2:$P2
P4:$P4
P6:$P6
EOF

test_expect_success 'pack 2, 4, and 6 are redundant' '
	git pack-redundant --all >out &&
	format_packfiles <out >actual &&
	test_cmp expected actual
'

test_expect_success 'create pack 8' '
	create_pack_8
'

cat >expected <<EOF
P2:$P2
P4:$P4
P6:$P6
P8:$P8
EOF

test_expect_success 'pack-8 (subset of pack-1) is also redundant' '
	git pack-redundant --all >out &&
	format_packfiles <out >actual &&
	test_cmp expected actual
'

test_expect_success 'clean loose objects' '
	git prune-packed &&
	find objects -type f | sed -e "/objects\/pack\//d" >out &&
	test_must_be_empty out
'

test_expect_success 'remove redundant packs and pass fsck' '
	git pack-redundant --all | xargs rm &&
	git fsck --no-progress &&
	git pack-redundant --all >out &&
	test_must_be_empty out
'

test_expect_success 'setup shared.git' '
	cd "$TRASH_DIRECTORY" &&
	git clone -q --mirror master.git shared.git &&
	cd shared.git &&
	printf "../../master.git/objects" >objects/info/alternates
'

test_expect_success 'no redundant packs without --alt-odb' '
	git pack-redundant --all >out &&
	test_must_be_empty out
'

cat >expected <<EOF
P1:$P1
P3:$P3
P5:$P5
P7:$P7
EOF

test_expect_success 'pack-redundant --verbose: show duplicate packs in stderr' '
	git pack-redundant --all --verbose >out 2>out.err &&
	test_must_be_empty out &&
	grep "pack$" out.err | format_packfiles >actual &&
	test_cmp expected actual
'

cat >expected <<EOF
fatal: Zero packs found!
EOF

test_expect_success 'remove redundant packs by alt-odb, no packs left' '
	git pack-redundant --all --alt-odb | xargs rm &&
	git fsck --no-progress &&
	test_must_fail git pack-redundant --all --alt-odb >actual 2>&1 &&
	test_cmp expected actual
'

create_commits_others () {
	parent=$(git rev-parse HEAD)
	for name in X Y Z
	do
		test_tick &&
		T=$(git write-tree) &&
		if test -z "$parent"
		then
			oid=$(echo $name | git commit-tree $T)
		else
			oid=$(echo $name | git commit-tree -p $parent $T)
		fi &&
		eval $name=$oid &&
		parent=$oid ||
		return 1
	done
	git update-ref refs/heads/master $Z
}

create_pack_x1 () {
	Px1=$(git -C objects/pack pack-objects -q pack <<-EOF
		$X
		$Y
		$Z
		$A
		$B
		$C
		EOF
	) &&
	eval P${Px1}=Px1:${Px1}
}

create_pack_x2 () {
	Px2=$(git -C objects/pack pack-objects -q pack <<-EOF
		$X
		$Y
		$Z
		$D
		$E
		$F
		EOF
	) &&
	eval P${Px2}=Px2:${Px2}
}

test_expect_success 'new objects and packs in shared.git' '
	create_commits_others &&
	create_pack_x1 &&
	create_pack_x2 &&
	git pack-redundant --all >out &&
	test_must_be_empty out
'

test_expect_success 'one pack is redundant' '
	git pack-redundant --all --alt-odb >out &&
	format_packfiles <out >actual &&
	test_line_count = 1 actual
'

cat >expected <<EOF
Px1:$Px1
Px2:$Px2
EOF

test_expect_success 'set ignore objects and all two packs are redundant' '
	git pack-redundant --all --alt-odb >out <<-EOF &&
		$X
		$Y
		$Z
		EOF
	format_packfiles <out >actual &&
	test_cmp expected actual
'

test_done
