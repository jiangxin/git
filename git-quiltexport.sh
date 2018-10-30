#bin/sh

OPTIONS_KEEPDASHDASH=
OPTIONS_STUCKLONG=
OPTIONS_SPEC="\
git quiltexport [options] <since> [HEAD]
--
patches=      path to the quilt patches
series=       path to the quilt series file
"

. git-sh-setup

is_since=

while test $# != 0
do
	case "$1" in
	--patches)
		shift
		QUILT_PATCHES="$1"
		;;
	--series)
		shift
		QUILT_SERIES="$1"
		;;
	--)
		shift
		break;;
	-*)
		usage
		;;
	*)
		break
		;;
	esac
	shift
done

case "$#" in
0)
	usage
	;;
1)
	case $1 in
	*..*)
		numOfCommits=$(git rev-list $1 | wc -l)
		;;
	^*)
		numOfCommits=$(git rev-list $1 HEAD | wc -l)
		;;
	*)
		numOfCommits=$(git rev-list $1..HEAD | wc -l)
		is_since=Yes
		;;
	esac
	;;
*)
	numOfCommits=$(git rev-list "$@" | wc -l)
	;;
esac

if test $? -ne 0
then
	printf >&2 "ERROR: fail to find commits from: $@\n"
	exit 1
fi

# Check number of pathes, no more than 100
if test "$numOfCommits" -eq 0
then
	printf >&2 "Nothing to export.\n"
	exit 0
elif test "$numOfCommits" -gt 100
then
	printf "Found ${numOfCommits} commits to be exported, are you sure? (y/n) "
	read input
	case $input in
	y|Y)
		break
		;;
	*)
		printf >&2 "Nothing to export.\n"
		exit 0
		;;
	esac
fi

# Quilt patch directory
: ${QUILT_PATCHES:=patches}
if test ! -d "$QUILT_PATCHES"
then
	mkdir -p "$QUILT_PATCHES"
fi

# Quilt series file
: ${QUILT_SERIES:=$QUILT_PATCHES/series}
if test -e "$QUILT_SERIES"
then
	printf >&2 "ERROR: the \"$QUILT_SERIES\" file already exist, export failed.\n"
	exit 1
fi

mkdir -p "$QUILT_PATCHES/t"
printf "Export patches:\n"
if test -z "$is_since"
then
	git format-patch -o "$QUILT_PATCHES/t" "$@" >"$QUILT_SERIES".lock &&
	sed -e "s#^${QUILT_PATCHES}/##g" < "$QUILT_SERIES".lock > "$QUILT_SERIES" &&
	rm "$QUILT_SERIES".lock
else
	git format-patch -o "$QUILT_PATCHES/t" $1..HEAD >"$QUILT_SERIES".lock &&
	sed -e "s#^${QUILT_PATCHES}/##g" < "$QUILT_SERIES".lock > "$QUILT_SERIES" &&
	rm "$QUILT_SERIES".lock
fi

if test $? -ne 0
then
	printf >&2 "ERROR: fail to run git-format-patch.\n"
	rm -f "$QUILT_SERIES"
	exit 1
else
	while read line
	do
		printf "\t$line\n"
	done < "$QUILT_SERIES"
fi
