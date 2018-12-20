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

static int get_loadavg(void)
{
	struct strbuf buf = STRBUF_INIT;
	char *loadavg, *p;
	FILE *fp;
	int percent;
	int ncpu;

#ifdef __APPLE__
	const char *argv[] = { "sysctl", "-n", "vm.loadavg", NULL };
	struct child_process cmd = CHILD_PROCESS_INIT;
#endif

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

	percent = atof(loadavg) / ncpu * 100;
	strbuf_release(&buf);
	return percent;
}

static int load_is_above_soft_limit(int load)
{
	return load >= LIMITING_SOFT_LOAD_THRESHOLD;
}

static int load_is_above_hard_limit(int load)
{
	return load >= LIMITING_HARD_LOAD_THRESHOLD;
}

/* sideband: 2 - progress, 3- error */
static void sideband_printf(int band, const char *fmt, ...)
{
	int sz;
	char msg[4096];

	bzero(msg, 4096);
	va_list params;
	va_start(params, fmt);

	if (band != 2 && band != 3) {
		xwrite(2, msg, sz);
	}

	if (band == 3) {
		sz = xsnprintf(msg, sizeof(msg), "%s", "error: ");
	} else {
		sz = xsnprintf(msg, sizeof(msg), "%s", "warning: ");
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
		} else if (retries > LIMITING_MAX_RETRY || load_is_above_hard_limit(loadavg)) {
			if (use_sideband)
				band = 3;
			if (retries > LIMITING_MAX_RETRY)
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
			sleep_secs = LIMITING_MIN_SLEEP_SECONDS + rand() % (LIMITING_MAX_SLEEP_SECONDS - LIMITING_MIN_SLEEP_SECONDS + 1);
			if (use_sideband)
				band = 2;
			sideband_printf(band,
					"Server load (%d%%) is high, waiting %d seconds [loop %d/%d]...\n",
					loadavg,
					sleep_secs,
					retries,
					LIMITING_MAX_RETRY);
			sleep(sleep_secs);
		}
		retries++;
	}
	return 0;
}
