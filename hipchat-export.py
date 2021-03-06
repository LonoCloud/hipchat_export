#!/usr/bin/env python
# encoding: utf-8
"""
hipchat_export.py

Created by Adam Mikeal on 2016-04-13.
Copyright (c) 2016 Adam Mikeal. All rights reserved.
"""

from __future__ import print_function

import requests
import sys
import io
import os
import getopt
import json

from datetime import datetime
from time import sleep, time

if sys.version_info[0] == 3:
    from urllib.parse import urlparse
else:
    from urlparse import urlparse

help_message = '''
A simple script to export 1-to-1 messages from HipChat using the v2 API
found at http://api.hipchat.com/v2.

Usage: python hipchat_export.py [options]

Options:
  -v                  Run verbosely
  -h, --help          Show this help file
  -l, --list          List the active users that will be queried
  -m, --messages      Messages only, without file uploads
  -u, --user_token    Your API user token
                        *** Generate this token online at
                        https://coa.hipchat.com/account/api ***
  -x, --extract_users User ID(s) to extract (comma separated list)

Examples:

  extract every 1-to-1 message:

  hipchat_export.py --user_token jKHxU8x6Jj25rTYaMuf6yTe7YpQ6TV413EUkBd0Z

  extract only 1-to-1 messages with certain users:

  hipchat_export.py --user_token jKHxU8x6Jj25rTYaMuf6yTe7YpQ6TV413EUkBd0Z --extract_users=123,456,789

After execution, a 'hipchat_export' folder will be created in the current
working directory, and folders will be created for each person it will ask
for 1-to-1 chat history (this list is determined by a dictionary in the main()
function). Uploaded binary files will be found in an 'uploads' folder, with a
path that partially matches the filepath recorded in the API data (the domain
and common URI path information is stripped).

The message data is stored as the raw JSON file, in files named 0.txt through
n.txt; as many as needed to fetch all the messages between you and that user.

NOTE: HipChat rate limits the API calls you can make with a user token to 100
call every 5 minutes. This script will track how many calls have been made to
the API, and before it hits 100 will insert a 5 minute pause.
'''

# Flag for verbosity
VERBOSE = False
# Flag for file uploads
GET_FILE_UPLOADS = True
EXPORT_DIR = os.path.join(os.getcwd(), 'hipchat_export')
FILE_DIR = os.path.join(EXPORT_DIR, 'uploads')
HIPCHAT_API_URL = "http://api.hipchat.com/v2"
REQUESTS_RATE_LIMIT = 100
TOTAL_REQUESTS = 0


def log(msg):
    if msg[0] == "\n":
        msg = msg[1:]
        log(' ')
    logit = '[%s] %s' % (datetime.now(), msg)
    print(logit.encode('utf8'))


def vlog(msg):
    if VERBOSE:
        log(msg)

def sleeper(delay):
    log(' ')
    for i in range(delay, -1, -1):
        sleep(1)
        sys.stdout.write("\r%d sec remaining to resume..." % i)
        sys.stdout.flush()
    print('')
    log("Script operation resuming...")

def take1():
    global TOTAL_REQUESTS
    global FETCH_START
    log("\nHipChat API rate limit reached. Script will pause for 1 minute")
    sleeper(60)
    TOTAL_REQUESTS = 0
    FETCH_START = time()

def take5():
    global TOTAL_REQUESTS
    global FETCH_START
    delay = ((5 * 60) - int(time() - FETCH_START)) + 10 # extra seconds
    log("\nScript will pause for the rest of the current 5 minute window")
    log("   (%d seconds remaining) and then resume." % delay)
    log("   Please do not kill the script during this pause -- I was too lazy to make")
    log("   it any smarter, so you'll have to start all over from the beginning... ;-)")
    sleeper(delay)
    TOTAL_REQUESTS = 0
    FETCH_START = time()


def check_requests_vs_limit():
    global REQUESTS_RATE_LIMIT
    global TOTAL_REQUESTS
    # Check TOTAL_REQUESTS vs the limit
    if TOTAL_REQUESTS > (REQUESTS_RATE_LIMIT - 2):
        take5()


def get_user_list(user_token):
    # Be sure to count each request to the API
    global TOTAL_REQUESTS
    global HIPCHAT_API_URL

    # Set HTTP header to use user token for auth
    headers = {'Authorization': 'Bearer ' + user_token}

    # Return value will be a dictionary
    user_list = {}

    # Fetch the user list from the API
    url = HIPCHAT_API_URL + "/user?max-results=1000"
    r = requests.get(url, headers=headers)
    TOTAL_REQUESTS += 1

    if 'error' in r.json():
        raise ApiError(r.json().get('error'))

    # Iterate through the users and make a dict to return
    for person in r.json()['items']:
        user_list[str(person['id'])] = person['name']

    # Return the dict
    return user_list


def display_userlist(user_list):
    print("\nThe following users are active and will be queried for 1-to-1 messages:\n")

    col_width = max([len(val) for val in user_list.values()]) + 2
    print("Name".ljust(col_width), "ID")
    print("-" * col_width + "--------")

    for u_id, name in user_list.items():
        print(name.ljust(col_width), u_id)


def message_export(user_token, user_id, user_name):
    # Set HTTP header to use user token for auth
    headers = {'Authorization': 'Bearer ' + user_token}

    # create dirs for current user
    dir_name = os.path.join(EXPORT_DIR, user_name)
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)
    dir_name = os.path.join(FILE_DIR, user_id)
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)

    # flag to control pagination
    MORE_RECORDS = True

    # flag to track iteration through pages
    LEVEL = 0

    # Check if we need to get file uploads
    global GET_FILE_UPLOADS

    # track the total number of requests made, so we can avoid the rate limit
    global TOTAL_REQUESTS
    # track time when we started this round of requests
    global FETCH_START

    # Set initial URL with correct user_id
    global HIPCHAT_API_URL
    url = HIPCHAT_API_URL + "/user/%s/history?date=%s&reverse=false" % (user_id, int(time()))

    # main loop to fetch and save messages
    FETCH_START = time()
    while MORE_RECORDS:
        # Check the REQ count...
        check_requests_vs_limit()

        # fetch the JSON data from the API
        vlog("Fetching URL: %s" % (url))
        r = requests.get(url, headers=headers)
        TOTAL_REQUESTS += 1

        # Check the REQ count...
        check_requests_vs_limit()

        # TODO - check response code for other errors and report out
        if (not r.status_code == requests.codes.ok) or ('error' in r.json()):
            if r.status_code == 429:
                # Hit the rate limit! trigger the 1m pause...
                take1()
                continue
            elif 'error' in r.json():
                if r.json()['error']['code'] == 429:
                    # Hit the rate limit! trigger the 1m pause...
                    take1()
                    continue
                else:
                    raise ApiError(r.json().get('error'))
            else:
                r.raise_for_status()

        # check JSON for objects and react
        if 'items' not in r.json():
            raise Usage("Could not find messages in API return data: %s" % (r.json()))

        # write the current JSON dump to file
        file_name = os.path.join(EXPORT_DIR, user_name, str(LEVEL) + '.txt')
        vlog("  + writing JSON to disk: %s" % (file_name))
        with io.open(file_name, 'w', encoding='utf-8') as f:
            f.write(json.dumps(r.json(), sort_keys=True, indent=4, ensure_ascii=False))

        if GET_FILE_UPLOADS:
            # scan for any file links (aws), fetch them and save to disk
            vlog("  + looking for file uploads in current message batch...")
            for item in r.json()['items']:
                if 'file' in item:
                    vlog("  + fetching file: %s" % (item['file']['url']))
                    r2 = requests.get(item['file']['url'])
                    TOTAL_REQUESTS += 1

                    # extract the unique part of the URI to use as a file name
                    fname = '/'.join(urlparse(item['file']['url']).path.split('/')[-3:])
                    fpath = os.path.join(FILE_DIR, fname)

                    # ensure full dir for the path exists
                    temp_d = os.path.dirname(fpath)
                    if not os.path.exists(temp_d):
                        os.makedirs(temp_d)

                    # now fetch the file and write it to disk
                    vlog("  --+ writing to disk: %s" % (fpath))
                    with open(fpath, 'w+b') as fd:
                        for chunk in r2.iter_content(1024):
                            fd.write(chunk)

                    # Check the REQ count...
                    check_requests_vs_limit()
                if 'authenticated_file' in item:
                    vlog("  + fetching file: %s" % (item['authenticated_file']['id']))
                    r2_pre = requests.get(HIPCHAT_API_URL + "/file/" + item['authenticated_file']['id'], headers={'Authorization': 'Bearer ' + user_token })
                    TOTAL_REQUESTS += 1

                    check_requests_vs_limit()

                    r2 = requests.get(r2_pre.json()['temp_url'])
                    TOTAL_REQUESTS += 1

                    # extract the unique part of the URI to use as a file name
                    fname = item['authenticated_file']['id'] + '_' + item['authenticated_file']['name']
                    fpath = os.path.join(FILE_DIR, fname)

                    # ensure full dir for the path exists
                    temp_d = os.path.dirname(fpath)
                    if not os.path.exists(temp_d):
                        os.makedirs(temp_d)

                    # now fetch the file and write it to disk
                    vlog("  --+ writing to disk: %s" % (fpath))
                    with open(fpath, 'w+b') as fd:
                        for chunk in r2.iter_content(1024):
                            fd.write(chunk)

                    # Check the REQ count...
                    check_requests_vs_limit()

        # check for more records to process
        if 'next' in r.json()['links']:
            url = r.json()['links']['next']
            LEVEL += 1
            sys.stdout.write("\rFetching range %d" % LEVEL)
            sys.stdout.flush()
        else:
            print('')
            MORE_RECORDS = False

            # end loop


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


class ApiError(Exception):
    pass


def main(argv=None):
    # initialize variables
    global GET_FILE_UPLOADS
    global VERBOSE
    ACTION = "PROCESS"
    USER_TOKEN = None
    IDS_TO_EXTRACT = None
    USER_LIST = {}
    USER_SUBSET = {}

    # create dir for binary files
    if not os.path.isdir(FILE_DIR):
        os.makedirs(FILE_DIR)

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hlmu:x:v",
                                       ["help", "list", "messages", "user_token=", "extract_users="])
        except getopt.error as msg:
            raise Usage(msg)

        # option processing
        for option, value in opts:
            if option in ("-h", "--help"):
                print(help_message)
                sys.exit(0)
            if option in ("-l", "--list"):
                ACTION = "DISPLAY"
            if option in ("-m", "--messages"):
                GET_FILE_UPLOADS = False
            if option == "-v":
                VERBOSE = True
            if option in ("-u", "--user_token"):
                USER_TOKEN = value
            if option in ("-x", "--extract_users"):
                IDS_TO_EXTRACT = value.split(',')

        # ensure that the token passed is a valid token length (real check happens later)
        if not USER_TOKEN or not len(USER_TOKEN) == 40:
            raise Usage("You must specify a valid HipChat user token!")

        # Get the list of users
        try:
            USER_LIST = get_user_list(USER_TOKEN)
        except ApiError as e:
            print("Hipchat API returned HTTP {code}/{type}: {message}".format(**e.message))
            return

        # Validate user IDs and ensure they are present in the user list
        if IDS_TO_EXTRACT:
            for user_id in IDS_TO_EXTRACT:
                try:
                    int(user_id)
                except ValueError:
                    print("Invald user ID: %s." % (user_id))
                    return 2

                if user_id not in USER_LIST.keys():
                    print("User ID %s not found in HipChat." % (user_id))
                    print("Using id rather than name for directory")
                    USER_SUBSET[user_id] = user_id
                else:
                    USER_SUBSET[user_id] = USER_LIST[user_id]

        # If the action is listing only, display and exit
        if ACTION == "DISPLAY":
            display_userlist(USER_LIST)
            sys.exit(0)

        # Iterate through user list and export all 1-to-1 messages to disk
        if USER_SUBSET:
            extract = USER_SUBSET.items()
        else:
            extract = USER_LIST.items()

        for user_id, user_name in extract:
            log("\nExporting 1-to-1 messages for %s (ID: %s)..." % (user_name, user_id))
            try:
                message_export(USER_TOKEN, user_id, user_name)
            except ApiError as e:
                print("Hipchat API returned HTTP {code}/{type}: {message}".format(**e.message))
                return

    except Usage as err:
        print("%s: %s" % (sys.argv[0].split("/")[-1], str(err.msg)), file=sys.stderr)
        print("\t for help use --help", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
