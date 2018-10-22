#include "../cache.h"
#include "refs-internal.h"

#define AGIT_REPO_WRITE_LOCK_FILE "agit-repo.lock"

/*
 * If this pre_check_hook failed (return no zero), ref transaction is denied,
 * and user cannot write to the repository.
 */
int refs_txn_pre_hook(struct ref_transaction *transaction) {
	struct strbuf dir_buf = STRBUF_INIT;
	struct strbuf lock_file = STRBUF_INIT;
	int ret = 0;
	char *dir;
	int fd;
	int len;
	int loop = 0;
	char err_msg[1024];

	if (!the_repository->gitdir)
		return 0;

	strbuf_addstr(&dir_buf, absolute_path(the_repository->gitdir));
	dir = dir_buf.buf;
	while (1) {
		loop++;
		strbuf_reset(&lock_file);

		if (!strcmp(dir, "/"))
			strbuf_addstr(&lock_file, "/" AGIT_REPO_WRITE_LOCK_FILE);
		else
			strbuf_addf(&lock_file, "%s/%s", dir, AGIT_REPO_WRITE_LOCK_FILE);

		if (!access(lock_file.buf, F_OK)) {
			error("cannot write to repository, locked by file '%s'",
			      AGIT_REPO_WRITE_LOCK_FILE);
			ret = 1;
			fd = open(lock_file.buf, O_RDONLY);
			if (fd != -1) {
				write_str_in_full(2, "\n");
				while ((len = read(fd, err_msg, 1024)) > 0)
					write_in_full(2, err_msg, len);
				write_str_in_full(2, "\n");
				close(fd);
			}
			break;
		}

		if (!strcmp(dir, "/") || loop > 20)
			break;

		dir = dirname(dir);
	}

	strbuf_release(&dir_buf);
	strbuf_release(&lock_file);

	return ret;
}
