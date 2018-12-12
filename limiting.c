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
#include <sys/sysinfo.h>

#include "cache.h"
#include "limiting.h"
#include "pkt-line.h"
#include "sideband.h"

static int get_loadavg(void)
{
	char load1[10];
	char *p;
	FILE *fp;
	double load1f;
	int ncpu = get_nprocs();

	bzero(load1, 10);
	fp = fopen("/proc/loadavg","r");
	if (fp == NULL)
		return -1;
	if (!fread(load1, 1, 8, fp)) {
		fclose(fp);
		return 0;
	}
	fclose(fp);

	for (int i = 0; i < 8; i++) {
		if (load1[i] == ' ') {
			load1[i] = '\0';
			break;
		}
	}
	load1f = atof(load1);
	return load1f / ncpu * 100;
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
