test_expect_success "setup proc-receive hook (multiple alt, no alt-ref for the 1st resp, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic old-oid=$A new-oid=$B" \
		-r "alt refs/for/master/topic refs/changes/24/124/1 old-oid=$ZERO_OID new-oid=$A" \
		-r "alt refs/for/master/topic refs/changes/25/125/1 old-oid=$A new-oid=$B"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic(A)
test_expect_success "proc-receive: report multiple alt, no alt-ref for the 1st resp ($PROTOCOL)" '
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
	remote: proc-receive> alt refs/for/master/topic refs/changes/24/124/1 old-oid=<ZERO-OID> new-oid=<COMMIT-A>
	remote: proc-receive> alt refs/for/master/topic refs/changes/25/125/1 old-oid=<COMMIT-A> new-oid=<COMMIT-B>
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/for/master/topic
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/changes/24/124/1
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/changes/25/125/1
	To <URL/of/upstream.git>
	 <OID-A>..<OID-B> HEAD -> refs/for/master/topic
	 * [new reference] HEAD -> refs/changes/24/124/1
	 <OID-A>..<OID-B> HEAD -> refs/changes/25/125/1
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (multiple alt, no alt-ref for the 2nd resp, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic refs/changes/24/124/1 old-oid=$ZERO_OID new-oid=$A" \
		-r "alt refs/for/master/topic old-oid=$A new-oid=$B" \
		-r "alt refs/for/master/topic refs/changes/25/125/1 old-oid=$B new-oid=$A forced-update"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic(A)
test_expect_success "proc-receive: report multiple alt, no alt-ref for the 2nd resp ($PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic refs/changes/24/124/1 old-oid=<ZERO-OID> new-oid=<COMMIT-A>
	remote: proc-receive> alt refs/for/master/topic old-oid=<COMMIT-A> new-oid=<COMMIT-B>
	remote: proc-receive> alt refs/for/master/topic refs/changes/25/125/1 old-oid=<COMMIT-B> new-oid=<COMMIT-A> forced-update
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/changes/24/124/1
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/for/master/topic
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/changes/25/125/1
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/changes/24/124/1
	 <OID-A>..<OID-B> HEAD -> refs/for/master/topic
	 + <OID-B>...<OID-A> HEAD -> refs/changes/25/125/1 (forced update)
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (ok and alt for the same ref, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "ok refs/for/master/topic" \
		-r "alt refs/for/master/topic refs/changes/24/124/1 new-oid=$B old-oid=$A"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic(A)
test_expect_success "proc-receive: report ok and alt for the same ref ($PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> ok refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic refs/changes/24/124/1 new-oid=<COMMIT-B> old-oid=<COMMIT-A>
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/changes/24/124/1
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/for/master/topic
	 <OID-A>..<OID-B> HEAD -> refs/changes/24/124/1
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "setup proc-receive hook (multiple responses, $PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "alt refs/for/master/topic refs/changes/23/123/1" \
		-r "alt refs/for/master/topic refs/changes/24/124/2 old-oid=$A new-oid=$B"
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git push         :                       refs/for/master/topic(A)
test_expect_success "proc-receive: report multiple response ($PROTOCOL)" '
	git -C workbench push origin \
		HEAD:refs/for/master/topic \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: # proc-receive hook
	remote: proc-receive< <ZERO-OID> <COMMIT-A> refs/for/master/topic
	remote: proc-receive> alt refs/for/master/topic refs/changes/23/123/1
	remote: proc-receive> alt refs/for/master/topic refs/changes/24/124/2 old-oid=<COMMIT-A> new-oid=<COMMIT-B>
	remote: # post-receive hook
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/changes/23/123/1
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/changes/24/124/2
	To <URL/of/upstream.git>
	 * [new reference] HEAD -> refs/changes/23/123/1
	 <OID-A>..<OID-B> HEAD -> refs/changes/24/124/2
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'
