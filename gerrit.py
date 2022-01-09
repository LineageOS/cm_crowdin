#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# gerrit.py
#
# Helper script for processing translation patches on
# LineageOS' gerrit
#
# Copyright (C) 2019-2022 The LineageOS Project
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

import utils


def submit(branch, username, owner):
    # If an owner is specified, modify the query, so we only get the ones wanted
    owner_arg = ""
    if owner is not None:
        owner_arg = f"owner:{owner}"

    # Find all open translation changes
    cmd = [
        "ssh",
        "-p",
        "29418",
        f"{username}@review.lineageos.org",
        "gerrit",
        "query",
        "status:open",
        f"branch:{branch}",
        owner_arg,
        'message:"Automatic translation import"',
        "topic:translation",
        "--current-patch-set",
        "--format=JSON",
    ]
    commits = 0
    msg, code = utils.run_subprocess(cmd)
    if code != 0:
        print(f"Failed: {msg[1]}")
        return

    # Each line is one valid JSON object, except the last one, which is empty
    for line in msg[0].strip("\n").split("\n"):
        js = json.loads(line)
        # We get valid JSON, but not every result line is one we want
        if "currentPatchSet" not in js or "revision" not in js["currentPatchSet"]:
            continue
        # Add Code-Review +2 and Verified+1 labels and submit
        cmd = [
            "ssh",
            "-p",
            "29418",
            f"{username}@review.lineageos.org",
            "gerrit",
            "review",
            "--verified +1",
            "--code-review +2",
            "--submit",
            js["currentPatchSet"]["revision"],
        ]
        msg, code = utils.run_subprocess(cmd, True)
        print("Submitting commit %s: " % js["url"], end="")
        if code != 0:
            error_text = msg[1].replace("\n\n", "; ").replace("\n", "")
            print(f"Failed: {error_text}")
        else:
            print("Success")

        commits += 1

    if commits == 0:
        print("Nothing to submit!")
        return
