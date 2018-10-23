#include "../repository.h"
#include "../cache.h"

#define AGIT_REPO_INFO_TIMESTAMP  "last-modified"

/*
 * If this pre_check_hook failed (return no zero), ref transaction is denied,
 * and user cannot write to the repository.
 */
int ref_transaction_pre_check_hook(struct strbuf *err) {
	/* TODO: run permission check, etc. */
	return 0;
}

/*
 * After ref_transaction finished successfully, run this post_action hook,
 * which will update a timestamp file to record last modified time.
 */
void ref_transaction_post_action_hook() {
	struct strbuf ts_file = STRBUF_INIT;
	struct stat fstat;
	int fd;

	if (!the_repository->gitdir)
		return;

	/* Create .git/info dir if not exist */
	strbuf_addf(&ts_file, "%s/%s", the_repository->gitdir, "info");
	if (access(ts_file.buf, F_OK)) {
		if (mkdir(ts_file.buf, 0775)) {
			error("cannot create dir '%s'", ts_file.buf);
			goto cleanup;
		}
	}

	/* Create .git/info/last-modified file if not exist */
	strbuf_addstr(&ts_file, "/" AGIT_REPO_INFO_TIMESTAMP);
	if (access(ts_file.buf, F_OK)) {
		int fd = creat(ts_file.buf, 0644);
		if (fd < 0)
			error("fail to create file %s", ts_file.buf);
		else
			close(fd);
		goto cleanup;
	}

	if (stat(ts_file.buf, &fstat)) {
		error("fail to stat %s", ts_file.buf);
		goto cleanup;
	}

	if (utimes(ts_file.buf, NULL)) {
		error("fail to change mtime of %s", ts_file.buf);
		goto cleanup;
	}

cleanup:
	strbuf_release(&ts_file);
	return;
}
