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

#define LIMITING_SOFT_LOAD_THRESHOLD	150
#define LIMITING_HARD_LOAD_THRESHOLD	300
#define LIMITING_MAX_RETRY 		3
#define LIMITING_MIN_SLEEP_SECONDS	10
#define LIMITING_MAX_SLEEP_SECONDS	60

extern int wait_for_avail_loadavg(int);

#endif
