test_expect_success "config receive.procReceiveRefs = refs ($PROTOCOL)" '
	git -C "$upstream" config --unset-all receive.procReceiveRefs &&
	git -C "$upstream" config --add receive.procReceiveRefs refs
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
test_expect_success "setup upstream branches ($PROTOCOL)" '
	(
		cd "$upstream" &&
		git update-ref refs/heads/master $B &&
		git update-ref refs/heads/foo $A &&
		git update-ref refs/heads/bar $A &&
		git update-ref refs/heads/baz $A
	)

'

test_expect_success "setup proc-receive hook ($PROTOCOL)" '
	write_script "$upstream/hooks/proc-receive" <<-EOF
	printf >&2 "# proc-receive hook\n"
	test-tool proc-receive -v \
		-r "ft refs/heads/master" \
		-r "ft refs/heads/foo" \
		-r "ft refs/heads/bar" \
		-r "alt refs/for/master/topic refs/pull/123/head old-oid=$A new-oid=$B " \
		-r "alt refs/for/next/topic refs/pull/124/head old-oid=$B new-oid=$A forced-update"
	EOF
'

# Refs of upstream : master(B)             foo(A)  bar(A))  baz(A)
# Refs of workbench: master(A)  tags/v123
# git push -f      : master(A)             (NULL)  (B)              refs/for/master/topic(A)  refs/for/next/topic(A)
test_expect_success "proc-receive: process all refs ($PROTOCOL)" '
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
	remote: proc-receive> ft refs/heads/master
	remote: proc-receive> ft refs/heads/foo
	remote: proc-receive> ft refs/heads/bar
	remote: proc-receive> alt refs/for/master/topic refs/pull/123/head old-oid=<COMMIT-A> new-oid=<COMMIT-B>
	remote: proc-receive> alt refs/for/next/topic refs/pull/124/head old-oid=<COMMIT-B> new-oid=<COMMIT-A> forced-update
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/heads/bar
	remote: post-receive< <COMMIT-A> <ZERO-OID> refs/heads/foo
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/heads/master
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/pull/123/head
	remote: post-receive< <COMMIT-B> <COMMIT-A> refs/pull/124/head
	To <URL/of/upstream.git>
	 <OID-A>..<OID-B> <COMMIT-B> -> bar
	 - [deleted] foo
	 + <OID-B>...<OID-A> HEAD -> master (forced update)
	 <OID-A>..<OID-B> HEAD -> refs/pull/123/head
	 + <OID-B>...<OID-A> HEAD -> refs/pull/124/head (forced update)
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

# Refs of upstream : master(A)             bar(A)  baz(B)
# Refs of workbench: master(A)  tags/v123
test_expect_success "cleanup ($PROTOCOL)" '
	(
		cd "$upstream" &&
		git update-ref -d refs/heads/bar &&
		git update-ref -d refs/heads/baz
	)
'
