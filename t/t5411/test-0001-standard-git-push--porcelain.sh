# Refs of upstream : master(A)  
# Refs of workbench: master(A)  tags/v123
# git-push         : master(B)             next(A)
test_expect_success "git-push ($PROTOCOL/porcelain)" '
	git -C workbench push --porcelain origin \
		$B:refs/heads/master \
		HEAD:refs/heads/next \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	remote: # pre-receive hook
	remote: pre-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	remote: pre-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	remote: # post-receive hook
	remote: post-receive< <COMMIT-A> <COMMIT-B> refs/heads/master
	remote: post-receive< <ZERO-OID> <COMMIT-A> refs/heads/next
	To <URL/of/upstream.git>
	     <COMMIT-B>:refs/heads/master    <OID-A>..<OID-B>
	*    HEAD:refs/heads/next    [new branch]
	Done
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-B> refs/heads/master
	<COMMIT-A> refs/heads/next
	EOF
	test_cmp expect actual
'

# Refs of upstream : master(B)  next(A)
# Refs of workbench: master(A)           tags/v123
# git-push -f      : master(A)  NULL     tags/v123  refs/review/master/topic(A)  a/b/c(A)
test_expect_success "git-push -f ($PROTOCOL/porcelain)" '
	git -C workbench push --porcelain -f origin \
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
	+    HEAD:refs/heads/master    <OID-B>...<OID-A> (forced update)
	-    :refs/heads/next    [deleted]
	*    refs/tags/v123:refs/tags/v123    [new tag]
	*    HEAD:refs/review/master/topic    [new reference]
	*    HEAD:refs/heads/a/b/c    [new branch]
	Done
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
test_expect_success "cleanup ($PROTOCOL)" '
	(
		cd "$upstream" &&
		git update-ref -d refs/review/master/topic &&
		git update-ref -d refs/tags/v123 &&
		git update-ref -d refs/heads/a/b/c
	)
'
