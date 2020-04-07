# Refs of upstream : master(B)  next(A)
# Refs of workbench: master(A)           tags/v123
# git-push -f      : master(A)  NULL     tags/v123  refs/review/master/topic(A)  a/b/c(A)
test_expect_success "normal git-push command" '
	git -C workbench push -f origin \
		refs/tags/v123 \
		:refs/heads/next \
		HEAD:refs/heads/master \
		HEAD:refs/review/master/topic \
		HEAD:refs/heads/a/b/c \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <COMMIT-B> <COMMIT-A> refs/heads/master
	remote: pre-receive< <COMMIT-A> <ZERO-OID> refs/heads/next
	remote: pre-receive< <ZERO-OID> <TAG-v123> refs/tags/v123
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/review/master/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/a/b/c
	remote: # post-receive hook
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/heads/master
	remote: post-receive< <COMMIT-A> <ZERO-OID> refs/heads/next
	remote: post-receive< <ZERO-OID> <TAG-v123> refs/tags/v123
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/review/master/topic
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/a/b/c
	To <URL/of/upstream.git>
	 + <OID>...<OID> HEAD -> master (forced update)
	 - [deleted] next
	 * [new tag] v123 -> v123
	 * [new reference] HEAD -> refs/review/master/topic
	 * [new branch] HEAD -> a/b/c
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/a/b/c
	<COMMIT-A> refs/heads/master
	<COMMIT-A> refs/review/master/topic
	<TAG-v123> refs/tags/v123
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(A)  tags/v123  refs/review/master/topic(A)  a/b/c(A)
# Refs of workbench: master(A)  tags/v123
test_expect_success "cleanup" '
	(
		cd "$upstream" &&
		git update-ref -d refs/review/master/topic &&
		git update-ref -d refs/tags/v123 &&
		git update-ref -d refs/heads/a/b/c
	)
'

test_expect_success "add two receive.procReceiveRefs settings" '
	(
		cd "$upstream" &&
		git config --add receive.procReceiveRefs refs/for &&
		git config --add receive.procReceiveRefs refs/review/
	)
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       next(A)  refs/for/master/topic(A)
test_expect_success "no proc-receive hook, fail to push special ref" '
	test_must_fail git -C workbench push origin \
		HEAD:next \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: error: cannot find hook "proc-receive"
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	To <URL/of/upstream.git>
	 * [new branch] HEAD -> next
	 ! [remote rejected] HEAD -> refs/for/master/topic (fail to run proc-receive hook)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	<COMMIT-A> refs/heads/next
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(A)             next(A)
# Refs of workbench: master(A)  tags/v123
test_expect_success "cleanup" '
	git -C "$upstream" update-ref -d refs/heads/next
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push --atomic: (B)                   next(A)  refs/for/master/topic(A)
test_expect_success "no proc-receive hook, fail all for atomic push" '
	test_must_fail git -C workbench push --atomic origin \
		$B:master \
		HEAD:next \
		HEAD:refs/for/master/topic >out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: error: cannot find hook "proc-receive"
	To <URL/of/upstream.git>
	 ! [remote rejected] <COMMIT-B> -> master (fail to run proc-receive hook)
	 ! [remote rejected] HEAD -> next (fail to run proc-receive hook)
	 ! [remote rejected] HEAD -> refs/for/master/topic (fail to run proc-receive hook)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (bad version)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF &&
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v --version 2
	EOF
	chmod a+x "$upstream/hooks/proc-receive"
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic(A)
test_expect_success "proc-receive bad protocol: unknown version" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&

	# Check status report for git-push
	sed -n \
		-e "/^To / { s/   */ /g; p; }" \
		-e "/^ / { s/   */ /g; p; }" \
		<actual >actual-report &&
	cat >expect <<-EOF &&
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (fail to run proc-receive hook)
	EOF
	test_cmp expect actual-report &&

	# Check error message from "receive-pack", but ignore unstable fatal error
	# message ("remote: fatal: the remote end hung up unexpectedly") which
	# is different from the remote HTTP server with different locale settings.
	sed -n -e "/^remote: error:/ { s/   */ /g; p; }" \
		<actual >actual-error &&
	cat >expect <<-EOF &&
	remote: error: proc-receive version "2" is not supported
	EOF
	test_cmp expect actual-error &&

	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (no report)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       next(A)  refs/for/master/topic(A)
test_expect_success "proc-receive bad protocol: no report" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/heads/next \
		HEAD:refs/for/master/topic >out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	To <URL/of/upstream.git>
	 * [new branch] HEAD -> next
	 ! [remote rejected] HEAD -> refs/for/master/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	<COMMIT-A> refs/heads/next
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(A)             next(A)
# Refs of workbench: master(A)  tags/v123
test_expect_success "cleanup" '
	git -C "$upstream" update-ref -d refs/heads/next

'

test_expect_success "setup proc-receive hook (bad oid)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "bad-id new-id ref ok"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive bad protocol: bad oid" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic\
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> bad-id new-id ref ok
	remote: error: proc-receive expected "old new ref status [msg]", got "bad-id new-id ref ok"
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (no status)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive bad protocol: no status" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: error: proc-receive expected "old new ref status [msg]", got "<ZERO-OID> <COMMIT-A> refs/for/master/topic"
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (unknown status)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic xx msg"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive bad protocol: unknown status" '
	test_must_fail git -C workbench push origin \
			HEAD:refs/for/master/topic \
			>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic xx msg
	remote: error: proc-receive has bad status "xx" for "<ZERO-OID> <COMMIT-A> refs/for/master/topic"
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (bad status)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic bad status"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive bad protocol: bad status" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic bad status
	remote: error: proc-receive has bad status "bad status" for "<ZERO-OID> <COMMIT-A> refs/for/master/topic"
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (ng)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic ng"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive: fail to update (no message)" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ng
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (failed)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (ng message)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic ng error msg"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive: fail to update (has message)" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ng error msg
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (error msg)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (report status on builtin command)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/heads/master ok"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         : (B)                   refs/for/master/topic
test_expect_success "proc-receive: warning on report for builtin command" '
	test_must_fail git -C workbench push origin \
		$B:refs/heads/master \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/heads/master ok
	remote: error: proc-receive reported status on ref of builtin command: refs/heads/master
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	To <URL/of/upstream.git>
	 <OID>..<OID> <COMMIT-B> -> master
	 ! [remote rejected] HEAD -> refs/for/master/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-B> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "cleanup" '
	git -C "$upstream" update-ref refs/heads/master $A
'

test_expect_success "setup proc-receive hook (ok)" '
	cat >"$upstream/hooks/proc-receive" <<-EOF
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/master/topic ok"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic
test_expect_success "proc-receive: ok" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/a/b/c/my/topic
test_expect_success "proc-receive: no report from proc-receive" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/a/b/c/my/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/a/b/c/my/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/a/b/c/my/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ok
	remote: error: proc-receive reported status on unknown ref: refs/for/master/topic
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/a/b/c/my/topic (no report from proc-receive)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push -o ...  :                       refs/for/master/topic
test_expect_success "not support push options" '
	test_must_fail git -C workbench push \
		-o issue=123 \
		-o reviewer=user1 \
		origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	test_i18ngrep "fatal: the receiving end does not support push options" \
		actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "enable push options" '
	git -C "$upstream" config receive.advertisePushOptions true
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push -o ...  :                       next(A)  refs/for/master/topic
test_expect_success "push with options" '
	git -C workbench push \
		--atomic \
		-o issue=123 \
		-o reviewer=user1 \
		origin \
		HEAD:refs/heads/next \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive: atomic push_options
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive< issue=123
	remote: proc-receive< reviewer=user1
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	To <URL/of/upstream.git>
	 * [new branch] HEAD -> next
	 * [new reference] HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	<COMMIT-A> refs/heads/next
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(A)             next(A)
# Refs of workbench: master(A)  tags/v123
test_expect_success "cleanup" '
	git -C "$upstream" update-ref -d refs/heads/next
'

test_expect_success "setup proc-receive hook" '
	cat >"$upstream/hooks/proc-receive" <<-EOF &&
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/review/a/b/c/topic ok" \
		-r "$ZERO_OID $A refs/for/next/topic ok ref:refs/pull/123/head" \
		-r "$ZERO_OID $A refs/for/master/topic ok ref:refs/pull/124/head"
	EOF
	chmod a+x "$upstream/hooks/proc-receive"
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/review/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "report update of all special refs" '
	git -C workbench push origin \
		HEAD:refs/for/next/topic \
		HEAD:refs/review/a/b/c/topic \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/review/a/b/c/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/review/a/b/c/topic
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/review/a/b/c/topic ok
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/next/topic ok ref:refs/pull/123/head
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ok ref:refs/pull/124/head
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/review/a/b/c/topic
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/pull/123/head
	 * [new reference] HEAD -> refs/review/a/b/c/topic
	 * [new reference] HEAD -> refs/pull/124/head
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook" '
	cat >"$upstream/hooks/proc-receive" <<-EOF &&
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$ZERO_OID $A refs/for/next/topic ok" \
		-r "$ZERO_OID $A refs/for/master/topic ok"
	EOF
	chmod a+x "$upstream/hooks/proc-receive"
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       bar(A)  baz(A)  refs/for/next/topic(A)  foo(A)  refs/for/master/topic(A)
test_expect_success "report mixed refs update" '
	git -C workbench push origin \
		$B:refs/heads/master \
		HEAD:refs/heads/bar \
		HEAD:refs/heads/baz \
		HEAD:refs/for/next/topic \
		HEAD:refs/heads/foo \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/bar
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/baz
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/foo
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/next/topic ok
	remote: proc-receive> <ZERO-OID> <COMMIT-A> refs/for/master/topic ok
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/bar
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/baz
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/foo
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	To <URL/of/upstream.git>
	 <OID>..<OID> <COMMIT-B> -> master
	 * [new branch] HEAD -> bar
	 * [new branch] HEAD -> baz
	 * [new reference] HEAD -> refs/for/next/topic
	 * [new branch] HEAD -> foo
	 * [new reference] HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/bar
	<COMMIT-A> refs/heads/baz
	<COMMIT-A> refs/heads/foo
	<COMMIT-B> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "config receive.procReceiveRefs for all ref/" '
	git -C "$upstream" config --add receive.procReceiveRefs refs/
'

test_expect_success "setup proc-receive hook" '
	cat >"$upstream/hooks/proc-receive" <<-EOF &&
	#!/bin/sh

	printf >&2 "# proc-receive hook\n"

	test-tool proc-receive -v \
		-r "$B $A refs/heads/master ft" \
		-r "$A $ZERO_OID refs/heads/foo ft" \
		-r "$A $B refs/heads/bar ft" \
		-r "$A $B refs/for/master/topic ok ref:refs/pull/123/head" \
		-r "$B $A refs/for/next/topic ok ref:refs/pull/124/head"
	EOF
	chmod a+x "$upstream/hooks/proc-receive"
'

# Refs of upstream : master(B)             foo(A)  bar(A))  baz(A)
# Refs of workbench: master(A)  tags/v123
# git push -f      :                       (NULL)  (B)              refs/for/master/topic(A)  refs/for/next/topic(A)
test_expect_success "report test: fallthrough" '
	git -C workbench push -f origin \
		HEAD:refs/heads/master \
		:refs/heads/foo \
		$B:refs/heads/bar \
		HEAD:refs/for/master/topic \
		HEAD:refs/for/next/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <COMMIT-A> <COMMIT-B> refs/heads/bar
	remote: pre-receive< <COMMIT-A> <ZERO-OID> refs/heads/foo
	remote: pre-receive< <COMMIT-B> <COMMIT-A> refs/heads/master
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: # proc-receive hook
	remote: proc-receive< <COMMIT-A> <COMMIT-B> refs/heads/bar
	remote: proc-receive< <COMMIT-A> <ZERO-OID> refs/heads/foo
	remote: proc-receive< <COMMIT-B> <COMMIT-A> refs/heads/master
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: proc-receive> <COMMIT-B> <COMMIT-A> refs/heads/master ft
	remote: proc-receive> <COMMIT-A> <ZERO-OID> refs/heads/foo ft
	remote: proc-receive> <COMMIT-A> <COMMIT-B> refs/heads/bar ft
	remote: proc-receive> <COMMIT-A> <COMMIT-B> refs/for/master/topic ok ref:refs/pull/123/head
	remote: proc-receive> <COMMIT-B> <COMMIT-A> refs/for/next/topic ok ref:refs/pull/124/head
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/heads/bar
	remote: post-receive< <COMMIT-A> <ZERO-OID> refs/heads/foo
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/heads/master
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/for/master/topic
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/for/next/topic
	To <URL/of/upstream.git>
	 <OID>..<OID> <COMMIT-B> -> bar
	 - [deleted] foo
	 + <OID>...<OID> HEAD -> master (forced update)
	 * [new reference] HEAD -> refs/pull/123/head
	 * [new reference] HEAD -> refs/pull/124/head
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-B> refs/heads/bar
	<COMMIT-A> refs/heads/baz
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'
