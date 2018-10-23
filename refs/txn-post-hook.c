#include "../cache.h"
#include "refs-internal.h"
#include "run-command.h"
#include "sigchain.h"

static GIT_PATH_FUNC(git_path_info_last_modified, "info/last-modified")

static int update_is_needed(struct ref_update *update) {
	if (update->flags & REF_LOG_ONLY)
		return 0;
	if (oideq(&update->old_oid, &update->new_oid))
		return 0;
	return 1;
}

static int update_is_needed_and_well_known(struct ref_update *update) {
	if (!update_is_needed(update))
		return 0;
	if (!strncmp(update->refname, "refs/heads/", 11) ||
	    !strncmp(update->refname, "refs/tags/", 10) ||
	    !strncmp(update->refname, "refs/change/", 12) ||
	    !strncmp(update->refname, "refs/changes/", 13) ||
	    !strncmp(update->refname, "refs/merge-requests/", 20) ||
	    !strncmp(update->refname, "refs/pull/", 10))
	       return 1;
	return 0;
}

/*
 * Create/update last_modified file for post action of files_transaction.
 */
static void refs_txn_post_update_last_modified(struct ref_transaction *transaction) {
	const char *filename = git_path_info_last_modified();
	int fd;
	int i;
	int has_change = 0;

	for (i = 0; i < transaction->nr; i++) {
		/*
		 * Do not update last-modified for trivial refs updates,
		 * such as: refs/tmp, refs/keep-around, ...
		 */
		if (update_is_needed_and_well_known(transaction->updates[i])) {
			has_change = 1;
			break;
		}
	}
	if (!has_change)
		return;

	/* Create .git/info/last-modified file if not exist */
	if (access(filename, F_OK)) {
		if (safe_create_leading_directories((char *)filename)) {
			error_errno(_("failed to create directories for '%s'"), filename);
			return;
		}
		fd = open(filename, O_CREAT | O_WRONLY, 0666);
		if (fd < 0) {
			error_errno("fail to create file %s", filename);
			return;
		}
		close(fd);
		adjust_shared_perm(filename);
	}

	if (utime(filename, NULL)) {
		error_errno("fail to change mtime for %s", filename);
	}
}

/*
 * Called from "reference-transaction committed" for our internal
 * refs post routines.
 */
void refs_txn_post_hook(struct ref_transaction *transaction) {
	if (!transaction->nr || !the_repository->gitdir)
		return;

	refs_txn_post_update_last_modified(transaction);
}
