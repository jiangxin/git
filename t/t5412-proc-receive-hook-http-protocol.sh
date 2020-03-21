#!/bin/sh
#
# Copyright (c) 2020 Jiang Xin
#

test_description='Test proc-receive hook for HTTP protocol'

. ./test-lib.sh

ROOT_PATH="$PWD"
. "$TEST_DIRECTORY"/lib-gpg.sh
. "$TEST_DIRECTORY"/lib-httpd.sh
. "$TEST_DIRECTORY"/lib-terminal.sh
start_httpd

. "$TEST_DIRECTORY"/t5411/common-functions.sh

# Format the output of git-push, git-show-ref and other commands to make a
# user-friendly and stable text.  In addition to the common format method,
# we also replace URL of different protocol for the upstream repository to
# a fixed pattern.
make_user_friendly_and_stable_output () {
	make_user_friendly_and_stable_output_common | sed \
		-e "s#To http:.*/upstream.git#To <URL/of/upstream.git>#"
}

# Refs of upstream : master(B)  next(A)
# Refs of workbench: master(A)           tags/v123
test_expect_success "setup" '
	git init --bare upstream.git &&
	git -C upstream.git config http.receivepack true &&
	git init workbench &&
	create_commits_in workbench A B &&
	(
		cd workbench &&
		# Try to make a stable fixed width for abbreviated commit ID,
		# this fixed-width oid will be replaced with "<OID>".
		git config core.abbrev 7 &&
		git remote add origin ../upstream.git &&
		git update-ref refs/heads/master $A &&
		git tag -m "v123" v123 $A &&
		git push origin \
			$B:refs/heads/master \
			$A:refs/heads/next
	) &&
	TAG=$(git -C workbench rev-parse v123) &&

	# setup pre-receive hook
	cat >upstream.git/hooks/pre-receive <<-\EOF &&
	#!/bin/sh

	echo >&2 "# pre-receive hook"

	while read old new ref
	do
		echo >&2 "pre-receive< $old $new $ref"
	done
	EOF

	# setup post-receive hook
	cat >upstream.git/hooks/post-receive <<-\EOF &&
	#!/bin/sh

	echo >&2 "# post-receive hook"

	while read old new ref
	do
		echo >&2 "post-receive< $old $new $ref"
	done
	EOF

	chmod a+x \
		upstream.git/hooks/pre-receive \
		upstream.git/hooks/post-receive &&

	upstream="$HTTPD_DOCUMENT_ROOT_PATH/upstream.git" &&
	mv upstream.git "$upstream" &&
	git -C workbench remote set-url origin $HTTPD_URL/smart/upstream.git
'

setup_askpass_helper

# Include test cases for both file and HTTP protocol
. "$TEST_DIRECTORY"/t5411/common-test-cases.sh

test_done
