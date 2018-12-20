/*
 * =====================================================================================
 *
 *       Filename:  limiting.h
 *
 *    Description:  git limiting protection
 *
 *        Version:  1.0
 *        Created:  12/10/18 17:08:03
 *       Revision:  1.0
 *       Compiler:  gcc
 *
 *         Author:  dyrone (dyroneteng), tenglong.tl@alibaba-inc.com
 *        Company:  Alibaba.com
 *
 * =====================================================================================
 */


#ifndef LIMITING_H
#define LIMITING_H

#define ENV_LOADAVG_SOFT_LIMIT		"AGIT_LOADAVG_SOFT_LIMIT"
#define ENV_LOADAVG_HARD_LIMIT		"AGIT_LOADAVG_HARD_LIMIT"
#define ENV_LOADAVG_SLEEP_MIN		"AGIT_LOADAVG_SLEEP_MIN"
#define ENV_LOADAVG_SLEEP_MAX		"AGIT_LOADAVG_SLEEP_MAX"
#define ENV_LOADAVG_RETRY		"AGIT_LOADAVG_RETRY"

#define DEFAULT_LOADAVG_SOFT_LIMIT	150
#define DEFAULT_LOADAVG_HARD_LIMIT	300
#define DEFAULT_LOADAVG_SLEEP_MIN	10
#define DEFAULT_LOADAVG_SLEEP_MAX	60
#define DEFAULT_LOADAVG_RETRY 		3

extern int wait_for_avail_loadavg(int);

#endif
