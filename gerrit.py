#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# gerrit.py
#
# Helper script for processing translation patches on
# LineageOS' gerrit
#
# Copyright (C) 2019-2025 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import re
import sys

import utils


def abandon(branch, username, owner, message):
    commits = 0
    changes = get_open_changes(branch, username, owner)
    for change in changes:
        logging.info(f"Abandoning commit {changes[change]}: ")
        # Abandon
        cmd = utils.get_gerrit_base_cmd(username) + [
            "review",
            "--abandon",
            change,
        ]
        if message:
            cmd += ["--message", f"'{message}'"]
        msg, code = utils.run_subprocess(cmd, True)
        if code != 0:
            error_text = msg[1].replace("\n\n", "; ").replace("\n", "")
            logging.warning(f"Failed! -- {error_text}")
        else:
            logging.info("Success")

        commits += 1

    if commits == 0:
        logging.info("Nothing to abandon!")


def submit(branch, username, owner):
    commits = 0
    changes = get_open_changes(branch, username, owner)
    for change in changes:
        logging.info(f"Submitting commit {changes[change]}")
        # Add Code-Review +2 and Verified+1 labels and submit
        cmd = utils.get_gerrit_base_cmd(username) + [
            "review",
            "--verified +1",
            "--code-review +2",
            "--submit",
            change,
        ]
        msg, code = utils.run_subprocess(cmd, True)
        if code != 0:
            error_text = msg[1].replace("\n\n", "; ").replace("\n", "")
            logging.error(f"Failed! -- {error_text}")
        else:
            logging.info("Success")

        commits += 1

    if commits == 0:
        logging.info("Nothing to submit!")


def vote(branch, username, owner, message):
    commits = 0
    changes = get_open_changes(branch, username, owner)
    for change in changes:
        logging.info(f"Voting on commit {changes[change]}: ")
        # Add Code-Review +1 and Verified+1 labels
        cmd = utils.get_gerrit_base_cmd(username) + [
            "review",
            "--verified +1",
            "--code-review +1",  # we often can't self-CR+2 (limited by admin), submitter needs to do that
            change,
        ]
        if message:
            cmd += ["--message", f"'{message}'"]
        msg, code = utils.run_subprocess(cmd, True)
        if code != 0:
            error_text = msg[1].replace("\n\n", "; ").replace("\n", "")
            logging.warning(f"Failed! -- {error_text}")
        else:
            logging.info("Success")

        commits += 1

    if commits == 0:
        logging.info("Nothing to vote on!")


def get_open_changes(branch, username, owner):
    logging.info("Fetching open changes on gerrit")

    # If an owner is specified, modify the query, so we only get the ones wanted
    owner_arg = "" if owner is None else f"owner:{owner}"

    # If branch is >= lineage-20.0, we want to also get lineage-20 changes
    if re.match("^lineage-[2-9]\d\.\d$", branch):
        branch_arg = f"(branch:{branch} or branch:{branch[:-2]})"
    else:
        branch_arg = f"branch:{branch}"

    # Find all open translation changes
    cmd = utils.get_gerrit_base_cmd(username) + [
        "query",
        "status:open",
        branch_arg,
        owner_arg,
        'message:"Automatic translation import"',
        "topic:translation",
        "--current-patch-set",
        "--format=JSON",
    ]
    msg, code = utils.run_subprocess(cmd)
    if code != 0:
        logging.warning(f"Failed: {msg[1]}")
        sys.exit(1)

    changes = {}
    # Each line is one valid JSON object, except the last one, which is empty
    for line in msg[0].strip("\n").split("\n"):
        try:
            js = json.loads(line)
            revision = js["currentPatchSet"]["revision"]
            changes[revision] = js["url"]
        except KeyError:
            continue
        except Exception as e:
            logging.exception(
                f"Failed to read revision from fetched dataset:\n{line}\n{e}"
            )

    return changes
