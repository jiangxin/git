test_expect_success "setup pre-receive hook (declined, $PROTOCOL)" '
	mv "$upstream/hooks/pre-receive" "$upstream/hooks/pre-receive.ok" &&
	write_script "$upstream/hooks/pre-receive" <<-EOF
	exit 1
	EOF
'

# Refs of upstream : master(A)
# Refs of workbench: master(A)  tags/v123
# git-push         : master(B)             next(A)
test_expect_success "git-push is declined (--porcelain, $PROTOCOL)" '
	test_must_fail git -C workbench push --porcelain origin \
		$B:refs/heads/master \
		HEAD:refs/heads/next \
		>out 2>&1 &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	To <URL/of/upstream.git>
	!    <COMMIT-B>:refs/heads/master    [remote rejected] (pre-receive hook declined)
	!    HEAD:refs/heads/next    [remote rejected] (pre-receive hook declined)
	Done
	EOF
	test_cmp expect actual &&
	git -C "$upstream" show-ref >out &&
	make_user_friendly_and_stable_output <out >actual &&
	cat >expect <<-EOF &&
	<COMMIT-A> refs/heads/master
	EOF
	test_cmp expect actual
'

test_expect_success "cleanup ($PROTOCOL)" '
	mv "$upstream/hooks/pre-receive.ok" "$upstream/hooks/pre-receive"
'
