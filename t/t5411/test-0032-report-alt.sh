test_expect_success "setup proc-receive hook (alt <ref>, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: report alt (alt <ref>, $PROTOCOL)" '
	test_must_fail git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic
	remote: error: proc-receive expected "alt <ref> <alt-ref> ...", got "alt refs/for/master/topic"
	To <URL/of/upstream.git>
	 ! [remote rejected] HEAD -> refs/for/master/topic (proc-receive failed to report status)
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (alt <ref> <alt-ref>, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic refs/pull/123/head"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: report alt (alt <ref> <alt-ref>, $PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic refs/pull/123/head
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/pull/123/head
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/pull/123/head
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (alt <ref> <alt-ref> forced-update, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic refs/pull/123/head forced-update"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: report alt (alt <ref> <alt-ref> forced-update, $PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic refs/pull/123/head forced-update
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/pull/123/head
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/pull/123/head
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (alt <ref> <alt-ref> old-oid=X, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic refs/pull/123/head old-oid=$B"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: report alt (alt <ref> <alt-ref> old-oid=X, $PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic refs/pull/123/head old-oid=<COMMIT-B>
	remote: # post-receive hook
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/pull/123/head
	To <URL/of/upstream.git>
	 <OID-B>..<OID-A> HEAD -> refs/pull/123/head
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (alt <ref> old-oid=X, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic old-oid=$B"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: report alt (alt <ref> old-oid=X, $PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic old-oid=<COMMIT-B>
	remote: # post-receive hook
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/for/master/topic
	To <URL/of/upstream.git>
	 <OID-B>..<OID-A> HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (alt <ref> old-oid=X new-oid=Y, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic old-oid=$A new-oid=$B"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: report alt (alt <ref> old-oid=X new-oid=Y, $PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic old-oid=<COMMIT-A> new-oid=<COMMIT-B>
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/for/master/topic
	To <URL/of/upstream.git>
	 <OID-A>..<OID-B> HEAD -> refs/for/master/topic
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (with multiple alt reports, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "ok refs/for/a/b/c/topic" \
		-r "alt refs/for/next/topic refs/pull/123/head" \
		-r "alt refs/for/master/topic refs/pull/124/head old-oid=$B forced-update new-oid=$A"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/next/topic(A)  refs/for/a/b/c/topic(A)  refs/for/master/topic(A)
test_expect_success "proc-receive: with multiple alt reports ($PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/next/topic \
		HEAD:refs/for/a/b/c/topic \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/a/b/c/topic
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/next/topic
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/a/b/c/topic
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> ok refs/for/a/b/c/topic
	remote: proc-receive> alt refs/for/next/topic refs/pull/123/head
	remote: proc-receive> alt refs/for/master/topic refs/pull/124/head old-oid=<COMMIT-B> forced-update new-oid=<COMMIT-A>
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/pull/123/head
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/a/b/c/topic
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/pull/124/head
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/pull/123/head
	 * [new reference] HEAD -> refs/for/a/b/c/topic
	 + <OID-B>...<OID-A> HEAD -> refs/pull/124/head (forced update)
	EOF
	test_cmp expect actual &&

	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'
