#!/bin/sh
#
# Copyright (c) 2018 Jiang Xin
#

test_description='git pack-redundant test'

. ./test-lib.sh

create_commits()
{
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
	git update-ref refs/heads/master $M
}

create_pack_1()
{
	P1=$(cd .git/objects/pack; printf "$T\n$A\n$B\n$C\n$D\n$E\n$F\n$R\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P1=P1:$P1
}

create_pack_2()
{
	P2=$(cd .git/objects/pack; printf "$B\n$C\n$D\n$E\n$G\n$H\n$I\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P2=P2:$P2
}

create_pack_3()
{
	P3=$(cd .git/objects/pack; printf "$F\n$I\n$J\n$K\n$L\n$M\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P3=P3:$P3
}

create_pack_4()
{
	P4=$(cd .git/objects/pack; printf "$J\n$K\n$L\n$M\n$P\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P4=P4:$P4
}

create_pack_5()
{
	P5=$(cd .git/objects/pack; printf "$G\n$H\n$N\n$O\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P5=P5:$P5
}

create_pack_6()
{
	P6=$(cd .git/objects/pack; printf "$N\n$O\n$Q\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P6=P6:$P6
}

create_pack_7()
{
	P7=$(cd .git/objects/pack; printf "$P\n$Q\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P7=P7:$P7
}

create_pack_8()
{
	P8=$(cd .git/objects/pack; printf "$A\n" | git pack-objects pack 2>/dev/null) &&
	eval P$P8=P8:$P8
}

test_expect_success 'setup' '
	create_commits
'

test_expect_success 'no redundant packs' '
	create_pack_1 && create_pack_2 && create_pack_3 &&
	git pack-redundant --all >out &&
	test_must_be_empty out
'

test_expect_success 'create pack 4, 5' '
	create_pack_4 && create_pack_5
'

cat >expected <<EOF
P2:$P2
EOF

test_expect_success 'one of pack-2/pack-3 is redundant' '
	git pack-redundant --all >out &&
	sed -E -e "s#.*/pack-(.*)\.(idx|pack)#\1#" out | \
		sort -u | \
		while read p; do eval echo "\${P$p}"; done | \
		sort >actual && \
	test_cmp expected actual
'

test_expect_success 'create pack 6, 7' '
	create_pack_6 && create_pack_7
'

cat >expected <<EOF
P2:$P2
P4:$P4
P6:$P6
EOF

test_expect_success 'pack 2, 4, and 6 are redundant' '
	git pack-redundant --all >out &&
	sed -E -e "s#.*/pack-(.*)\.(idx|pack)#\1#" out | \
		sort -u | \
		while read p; do eval echo "\${P$p}"; done | \
		sort >actual && \
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

test_expect_success 'pack-8, subset of pack-1, is also redundant' '
	git pack-redundant --all >out &&
	sed -E -e "s#.*/pack-(.*)\.(idx|pack)#\1#" out | \
		sort -u | \
		while read p; do eval echo "\${P$p}"; done | \
		sort >actual && \
	test_cmp expected actual
'

test_expect_success 'clear loose objects' '
	git prune-packed &&
	find .git/objects -type f | sed -e "/objects\/pack\//d" >out &&
	test_must_be_empty out
'

test_expect_success 'remove redundant packs' '
	git pack-redundant --all | xargs rm &&
	git fsck &&
	git pack-redundant --all >out &&
	test_must_be_empty out
'

test_done
