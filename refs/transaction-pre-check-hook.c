#include "../cache.h"
#include "refs-internal.h"

#define AGIT_REPO_WRITE_LOCK_FILE "agit-repo.lock"

/*
 * If this pre_check_hook failed (return no zero), ref transaction is denied,
 * and user cannot write to the repository.
 */
int ref_transaction_pre_check_hook(struct ref_transaction *transaction, struct strbuf *err) {
	struct strbuf dir_buf = STRBUF_INIT;
	struct strbuf lock_file = STRBUF_INIT;
	static int run_once = 0;
	static int ret = 0;
	char *dir;
	int fd;
	int len;
	int loop = 0;
	char err_msg[1024];
	char *env;

	if (run_once++) {
		strbuf_addstr(err, "repository is locked");
		return ret;
	}

	env = getenv("GIT_REFS_TXN_NO_HOOK");
	if ((env && !strcmp(env, "1")) || transaction->nr == 0)
		return 0;

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
			strbuf_addf(err, "cannot write to repository, locked by file '%s'.\n\n", AGIT_REPO_WRITE_LOCK_FILE);
			ret = 1;
			fd = open(lock_file.buf, O_RDONLY);
			if (fd != -1) {
				while ((len = read(fd, err_msg, 1024)) > 0) {
					strbuf_add(err, err_msg, len);
				}
				close(fd);
			}
			break;
		}

		if (!strcmp(dir, "/"))
			break;

		if (loop > 20) {
			break;
		}

		dir = dirname(dir);
	}

	strbuf_release(&dir_buf);
	strbuf_release(&lock_file);

	return ret;
}
