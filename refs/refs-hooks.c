#include "../cache.h"

/*
 * If this pre_check_hook failed (return no zero), ref transaction is denied,
 * and user cannot write to the repository.
 */
int ref_transaction_pre_check_hook(struct strbuf *err) {
	// TODO: Run permission check, etc.
	return 0;
}

/*
 * After ref_transaction finished successfully, run this post_action hook,
 * which will update a timestamp file to record last modified time.
 */
void ref_transaction_post_action_hook() {
	// TODO: update repo last-modified timestamp, etc.
	return;
}
