/*
 * =====================================================================================
 *
 *       Filename:  limiting.c
 *
 *    Description:  git limiting protection
 *
 *        Version:  1.0
 *        Created:  12/10/18 17:10:51
 *       Revision:  1.0
 *       Compiler:  gcc
 *
 *         Author:  dyrone (dyroneteng), tenglong.tl@alibaba-inc.com
 *        Company:  Alibaba.com
 *
 * =====================================================================================
 */


#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "cache.h"
#include "limiting.h"
#include "run-command.h"
#include "pkt-line.h"
#include "sideband.h"

#ifdef __APPLE__
  #include <sys/sysctl.h>
#else
  #include <sys/sysinfo.h>
#endif

static int getenv_int(char *env, int value)
{
	char *p = getenv(env);

	if (!p)
		return value;

	if (!strcmp(p, "yes") || !strcmp(p, "y") || !strcmp(p, "true") || !strcmp(p, "t"))
		return 1;
	else if (!strcmp(p, "no") || !strcmp(p, "n") || !strcmp(p, "false") || !strcmp(p, "f"))
		return 0;

	return atoi(p);
}

static int loadavg_test_dryrun(void)
{
	static int n = -1;

	if (n == -1)
		n = getenv_int(ENV_LOADAVG_TEST_DRYRUN, 0);
	return n;
}

/* AGIT_LOADAVG_TEST_MOCK=90,80,70 */
static int loadavg_test_mock(struct string_list *loadavg_list)
{
	char *item;
	char *p;

	if (loadavg_list->nr > 0)
		return 1;
	p = getenv(ENV_LOADAVG_TEST_MOCK);
	if (!p)
		return 0;
	for (item = strtok(p, ","); item; item = strtok(NULL, ","))
		string_list_append(loadavg_list, item);
	return 1;
}

static int get_loadavg_soft_limit(void)
{
	static int n = -1;

	if (n == -1)
		n = getenv_int(ENV_LOADAVG_SOFT_LIMIT,
				 DEFAULT_LOADAVG_SOFT_LIMIT);
	return n;
}

static int get_loadavg_hard_limit(void)
{
	static int n = -1;

	if (n == -1)
		n = getenv_int(ENV_LOADAVG_HARD_LIMIT,
				 DEFAULT_LOADAVG_HARD_LIMIT);
	return n;
}

static int get_loadavg_sleep_min(void)
{
	static int n = -1;

	if (n == -1)
		n = getenv_int(ENV_LOADAVG_SLEEP_MIN,
				 DEFAULT_LOADAVG_SLEEP_MIN);
	return n;
}

static int get_loadavg_sleep_max(void)
{
	static int n = -1;

	if (n == -1)
		n = getenv_int(ENV_LOADAVG_SLEEP_MAX,
				 DEFAULT_LOADAVG_SLEEP_MAX);
	return n;
}

static int get_loadavg_retry(void)
{
	static int n = -1;

	if (n == -1)
		n = getenv_int(ENV_LOADAVG_RETRY,
				 DEFAULT_LOADAVG_RETRY);
	return n;
}

static int get_loadavg(void)
{
	struct strbuf buf = STRBUF_INIT;
	char *loadavg, *p;
	int percent;
	int ncpu;
	static int count = 0;
	static struct string_list loadavg_list = STRING_LIST_INIT_DUP;

#ifdef __APPLE__
	const char *argv[] = { "sysctl", "-n", "vm.loadavg", NULL };
	struct child_process cmd = CHILD_PROCESS_INIT;
#else
	FILE *fp;
#endif

	if (loadavg_test_mock(&loadavg_list) && loadavg_list.nr >0) {
		if (count >= loadavg_list.nr) {
			count = loadavg_list.nr - 1;
		}

		percent = atoi(loadavg_list.items[count].string);
		count++;
		return percent;
	}
	
#ifdef __APPLE__
	/* cmd `sysctl -n vm.loadavg` returns: { 1.92 2.17 2.19 } */
	cmd.argv = argv;
	cmd.git_cmd = 0;
	cmd.in = 0;
	cmd.out = -1;

	if (start_command(&cmd))
		die("unable to spawn sysctl");

	if (strbuf_read(&buf, cmd.out, 20) < 0)
		die_errno("unable to read from sysctl");
	close(cmd.out);

	if (finish_command(&cmd))
		die("fail to finish sysctl");
#else
	fp = fopen("/proc/loadavg","r");
	if (fp == NULL)
		return -1;
	if (!strbuf_fread(&buf, 20, fp)) {
		fclose(fp);
		return 0;
	}
	fclose(fp);
#endif

/* Get cpu core number */
#ifdef __APPLE__
	{
		size_t len = sizeof(ncpu);
		sysctlbyname("hw.ncpu", &ncpu, &len, NULL, 0);
	}
#else
	ncpu = get_nprocs();
#endif

	p = buf.buf;
	while (*p && (*p == '{' || *p == ' ')) {
		p++;
	};
	loadavg = p;
	while (*(++p)) {
		if (*p == ' ') {
			*p = '\0';
			break;
		}
	}

	percent = 100 * atof(loadavg) / ncpu;
	strbuf_release(&buf);
	return percent;
}


static int load_is_above_soft_limit(int load)
{
	return load >= get_loadavg_soft_limit();
}

static int load_is_above_hard_limit(int load)
{
	return load >= get_loadavg_hard_limit();
}

/* sideband: 2 - progress, 3- error */
static void sideband_printf(int band, const char *fmt, ...)
{
	int sz = 0;
	char msg[4096];
	va_list params;

	bzero(msg, 4096);
	va_start(params, fmt);

	if (band != 2 && band != 3) {
		xwrite(2, msg, sz);
	}

	if (band == 3) {
		sz = xsnprintf(msg, sizeof(msg), "%s", "ERROR: ");
	} else {
		sz = xsnprintf(msg, sizeof(msg), "%s", "WARN: ");
	}
	sz += vsnprintf(msg + sz, sizeof(msg) - sz, fmt, params);
	if (sz > (sizeof(msg) - 1))
		sz = sizeof(msg) - 1;
	msg[sz++] = '\n';

	send_sideband(1, band, msg, sz, LARGE_PACKET_MAX);

	va_end(params);
}

int wait_for_avail_loadavg(int use_sideband)
{
	int retries = 1;
	int loadavg;
	int sleep_secs;
	int band = 0;

	while ((loadavg = get_loadavg())) {
		if (!load_is_above_soft_limit(loadavg)) {
			break;
		} else if (retries > get_loadavg_retry() || load_is_above_hard_limit(loadavg)) {
			if (use_sideband)
				band = 3;
			if (retries > get_loadavg_retry())
				sideband_printf(band,
						"Server load (%d%%) is still high, quilt",
						loadavg);
			else
				sideband_printf(band,
						"Server load (%d%%) is too high, quilt",
						loadavg);
			return 1;
		} else {
			srand(time(NULL));
			sleep_secs = get_loadavg_sleep_min() + rand() % (
					get_loadavg_sleep_max() -
					get_loadavg_sleep_min() +
					1);
			if (use_sideband)
				band = 2;
			sideband_printf(band,
					"Server load (%d%%) is high, waiting %d seconds [loop %d/%d]...",
					loadavg,
					sleep_secs,
					retries,
					get_loadavg_retry());
			if (loadavg_test_dryrun())
				sideband_printf(band, "Will sleep %d seconds...", sleep_secs);
			else
				sleep(sleep_secs);
		}
		retries++;
	}
	return 0;
}
