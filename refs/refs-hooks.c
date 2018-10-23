#include "../repository.h"
#include "../cache.h"

#define AGIT_REPO_WRITE_LOCK_FILE "agit-repo.lock"
#define AGIT_REPO_INFO_TIMESTAMP  "last-modified"

/*
 * If this pre_check_hook failed (return no zero), ref transaction is denied,
 * and user cannot write to the repository.
 */
int ref_transaction_pre_check_hook(struct strbuf *err) {
	struct strbuf dir_buf = STRBUF_INIT;
	struct strbuf lock_file = STRBUF_INIT;
	int ret = 0;
	int fd;
	int len;
	int loop = 0;
	char err_msg[1024];

	if (!the_repository->gitdir)
		return 0;

	strbuf_addstr(&dir_buf, absolute_path(the_repository->gitdir));
	while (1) {
		loop++;
		strbuf_reset(&lock_file);

		if (!strcmp(dir_buf.buf, "/"))
			strbuf_addstr(&lock_file, "/" AGIT_REPO_WRITE_LOCK_FILE);
		else
			strbuf_addf(&lock_file, "%s/%s", dir_buf.buf, AGIT_REPO_WRITE_LOCK_FILE);

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

		if (!strcmp(dir_buf.buf, "/"))
			break;

		if (loop > 20) {
			break;
		}

		dirname(dir_buf.buf);
	}

	strbuf_release(&dir_buf);
	strbuf_release(&lock_file);

	return ret;
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

	// Create .git/info dir if not exist
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
