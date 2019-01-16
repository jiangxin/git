#bin/sh

OPTIONS_KEEPDASHDASH=
OPTIONS_STUCKLONG=
OPTIONS_SPEC="\
git quiltexport [options] <since> [HEAD]
--
patches=      path to the quilt patches
series=       path to the quilt series file
"
SUBDIRECTORY_ON=Yes
. git-sh-setup

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
1)
	EXPORT_SINCE=$1
	EXPORT_HEAD=HEAD
	;;
2)
	EXPORT_SINCE=$1
	EXPORT_HEAD=$2
	;;
*)
	usage
	;;
esac

# Quilt patch directory
: ${QUILT_PATCHES:=patches}
if ! [ -d "$QUILT_PATCHES" ] ; then
	mkdir -p "$QUILT_PATCHES"
fi

# Quilt series file
: ${QUILT_SERIES:=$QUILT_PATCHES/series}
if [ -e "$QUILT_SERIES" ] ; then
	printf >&2 "ERROR: the \"$QUILT_SERIES\" file already exist, export failed.\n"
	exit 1
fi

# Check number of pathes, no more than 100
numOfCommits=$(git rev-list ${EXPORT_SINCE}..${EXPORT_HEAD} | wc -l)
if test $? -ne 0; then
	printf >&2 "ERROR: fail to find commits between ${EXPORT_SINCE} and ${EXPORT_HEAD}.\n"
	exit 1
fi

if test "$numOfCommits" -eq 0; then
	printf >&2 "Nothing to export.\n"
	exit 0
elif test "$numOfCommits" -gt 100; then
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

mkdir -p "$QUILT_PATCHES/t"
printf "Export patches from '$EXPORT_SINCE' to '$EXPORT_HEAD':\n"
git format-patch -o "$QUILT_PATCHES/t" ${EXPORT_SINCE}..${EXPORT_HEAD} | \
	sed -e "s#^${QUILT_PATCHES}/##g" > "$QUILT_SERIES"

if test $? -ne 0; then
	printf >&2 "ERROR: fail to run git-format-patch.\n"
	rm -f "$QUILT_SERIES"
	exit 1
else
	while read line; do
		printf "\t$line\n"
	done < "$QUILT_SERIES"
fi
