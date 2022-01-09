#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# crowdin_sync.py
#
# Updates Crowdin source translations and pushes translations
# directly to LineageOS' Gerrit.
#
# Copyright (C) 2014-2016 The CyanogenMod Project
# Copyright (C) 2017-2022 The LineageOS Project
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

# ################################# IMPORTS ################################## #

import argparse
import itertools
import json
import os
import sys
import time
import threading

from distutils.util import strtobool
from lxml import etree
from signal import signal, SIGINT
from subprocess import Popen, PIPE

import crowdin_download
from crowdin_download import get_extracted_files, upload_translations_gerrit

# ################################# GLOBALS ################################## #

_DIR = os.path.dirname(os.path.realpath(__file__))
_COMMITS_CREATED = False
_DONE = False

# ################################ FUNCTIONS ################################# #


def run_subprocess(cmd, silent=False, show_spinner=False):
    t = start_spinner(show_spinner)
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    comm = p.communicate()
    exit_code = p.returncode
    if exit_code != 0 and not silent:
        print(
            "There was an error running the subprocess.\n"
            "cmd: %s\n"
            "exit code: %d\n"
            "stdout: %s\n"
            "stderr: %s" % (cmd, exit_code, comm[0], comm[1]),
            file=sys.stderr,
        )
    stop_spinner(t)
    return comm, exit_code


def start_spinner(show_spinner):
    global _DONE
    _DONE = False
    if not show_spinner:
        return None
    t = threading.Thread(target=spin_cursor)
    t.start()
    return t


def stop_spinner(t):
    global _DONE
    if t is None:
        return
    _DONE = True
    t.join(1)


def spin_cursor():
    global _DONE
    spinner = itertools.cycle([".", "..", "...", "....", "....."])
    while not _DONE:
        sys.stdout.write("\x1b[1K\r")
        output = next(spinner)
        sys.stdout.write(output)
        sys.stdout.flush()
        time.sleep(0.5)
    sys.stdout.write("\x1b[1K\r     ")


def submit_gerrit(branch, username, owner):
    # If an owner is specified, modify the query so we only get the ones wanted
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
    msg, code = run_subprocess(cmd)
    if code != 0:
        print(f"Failed: {msg[1]}")
        return

    # Each line is one valid JSON object, except the last one, which is empty
    for line in msg[0].strip("\n").split("\n"):
        js = json.loads(line)
        # We get valid JSON, but not every result line is one we want
        if not "currentPatchSet" in js or not "revision" in js["currentPatchSet"]:
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
        msg, code = run_subprocess(cmd, True)
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


def check_run(cmd):
    p = Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    ret = p.wait()
    if ret != 0:
        joined = " ".join(cmd)
        print(f"Failed to run cmd: {joined}", file=sys.stderr)
        sys.exit(ret)


def find_xml(base_path):
    for dp, dn, file_names in os.walk(base_path):
        for f in file_names:
            if os.path.splitext(f)[1] == ".xml":
                yield os.path.join(dp, f)


def get_username(args):
    username = args.username
    if (args.submit or args.download) and username is None:
        # try getting the username from git
        msg, code = run_subprocess(
            ["git", "config", "--get", "review.review.lineageos.org.username"],
            silent=True,
        )
        has_username = False
        if code == 0:
            username = msg[0].strip("\n")
            if username != "":
                has_username = user_prompt(
                    f"Argument -u/--username was not specified but found '{username}', "
                    f"continue?"
                )
            else:
                print("Argument -u/--username is required!")
        if not has_username:
            sys.exit(1)
    return username


def user_prompt(question):
    while True:
        user_input = input(question + " [y/n]: ")
        try:
            return bool(strtobool(user_input))
        except ValueError:
            print("Please use y/n or yes/no.\n")


# ############################################################################ #


def parse_args():
    parser = argparse.ArgumentParser(
        description="Synchronising LineageOS' translations with Crowdin"
    )
    parser.add_argument("-u", "--username", help="Gerrit username")
    parser.add_argument("-b", "--branch", help="LineageOS branch", required=True)
    parser.add_argument("-c", "--config", help="Custom yaml config")
    parser.add_argument(
        "--upload-sources", action="store_true", help="Upload sources to Crowdin"
    )
    parser.add_argument(
        "--upload-translations",
        action="store_true",
        help="Upload translations to Crowdin",
    )
    parser.add_argument(
        "--download", action="store_true", help="Download translations from Crowdin"
    )
    parser.add_argument(
        "-s", "--submit", action="store_true", help="Merge open translation commits"
    )
    parser.add_argument(
        "-o", "--owner", help="Specify the owner of the commits to submit"
    )
    parser.add_argument(
        "-p",
        "--path-to-crowdin",
        help="Path to crowdin executable (will look in PATH by default)",
        default="crowdin",
    )
    return parser.parse_args()


# ################################# PREPARE ################################## #


def check_dependencies():
    # Check for Java version of crowdin
    cmd = ["which", "crowdin"]
    msg, code = run_subprocess(cmd, silent=True)
    if code != 0:
        print("You have not installed crowdin.", file=sys.stderr)
        return False
    return True


def load_xml(x):
    try:
        return etree.parse(x)
    except etree.XMLSyntaxError:
        print(f"Malformed {x}", file=sys.stderr)
        return None
    except Exception:
        print(f"You have no {x}", file=sys.stderr)
        return None


def check_files(files):
    for f in files:
        if not os.path.isfile(f):
            print(f"You have no {f}.", file=sys.stderr)
            return False
    return True


# ################################### MAIN ################################### #


def upload_sources_crowdin(branch, config_dict, crowdin_path):
    global _COMMITS_CREATED
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nUploading sources to Crowdin ({config_dict['headers'][i]})")
        cmd = [
            crowdin_path,
            "upload",
            "sources",
            f"--branch={branch}",
            f"--config={cfg}",
        ]
        comm, ret = run_subprocess(cmd, show_spinner=True)
        if ret != 0:
            print(f"Failed to upload:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)
    _COMMITS_CREATED = True


def upload_translations_crowdin(branch, config_dict, crowdin_path):
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nUploading translations to Crowdin ({config_dict['headers'][i]})")
        cmd = [
            crowdin_path,
            "upload",
            "translations",
            f"--branch={branch}",
            "--no-import-duplicates",
            "--import-eq-suggestions",
            "--auto-approve-imported",
            f"--config={cfg}",
        ]
        comm, ret = run_subprocess(cmd, show_spinner=True)
        if ret != 0:
            print(f"Failed to upload:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)


def download_crowdin(base_path, branch, xml, username, config_dict, crowdin_path):
    extracted = []
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nDownloading translations from Crowdin ({config_dict['headers'][i]})")
        cmd = [crowdin_path, "download", f"--branch={branch}", f"--config={cfg}"]
        comm, ret = run_subprocess(cmd, show_spinner=True)
        if ret != 0:
            print(f"Failed to download:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)
        extracted += get_extracted_files(comm[0], branch)

    upload_translations_gerrit(extracted, xml, base_path, branch, username)


def sig_handler(signal_received, frame):
    global _DONE
    print("")
    print("SIGINT or CTRL-C detected. Exiting gracefully")
    _DONE = True
    exit(0)


def main():
    global _COMMITS_CREATED
    signal(SIGINT, sig_handler)
    args = parse_args()
    default_branch = args.branch

    username = get_username(args)

    if args.submit:
        submit_gerrit(default_branch, username, args.owner)
        sys.exit(0)

    base_path_branch_suffix = default_branch.replace("-", "_").replace(".", "_").upper()
    base_path_env = f"LINEAGE_CROWDIN_BASE_PATH_{base_path_branch_suffix}"
    base_path = os.getenv(base_path_env)
    if base_path is None:
        cwd = os.getcwd()
        print(f"You have not set {base_path_env}. Defaulting to {cwd}")
        base_path = cwd
    if not os.path.isdir(base_path):
        print(f"{base_path_env} is not a real directory: {base_path}")
        sys.exit(1)

    if args.path_to_crowdin == "crowdin" and not check_dependencies():
        sys.exit(1)

    xml_android = load_xml(x=f"{base_path}/android/default.xml")
    if xml_android is None:
        sys.exit(1)

    xml_extra = load_xml(x=f"{_DIR}/config/{default_branch}_extra_packages.xml")
    if xml_extra is None:
        sys.exit(1)

    xml_snippet = load_xml(x=f"{base_path}/android/snippets/lineage.xml")
    if xml_snippet is None:
        xml_snippet = load_xml(x=f"{base_path}/android/snippets/cm.xml")
    if xml_snippet is None:
        xml_snippet = load_xml(x=f"{base_path}/android/snippets/hal_cm_all.xml")
    if xml_snippet is not None:
        xml_files = (xml_android, xml_snippet, xml_extra)
    else:
        xml_files = (xml_android, xml_extra)

    config_dict = {}
    if args.config:
        config_dict["headers"] = ["custom config"]
        config_dict["files"] = [f"{_DIR}/config/{args.config}"]
    else:
        config_dict["headers"] = [
            "AOSP supported languages",
            "non-AOSP supported languages",
        ]
        config_dict["files"] = [
            f"{_DIR}/config/{default_branch}.yaml",
            f"{_DIR}/config/{default_branch}_aosp.yaml",
        ]
    if not check_files(config_dict["files"]):
        sys.exit(1)

    if args.upload_sources:
        upload_sources_crowdin(default_branch, config_dict, args.path_to_crowdin)
    if args.upload_translations:
        upload_translations_crowdin(default_branch, config_dict, args.path_to_crowdin)
    if args.download:
        download_crowdin(
            base_path,
            default_branch,
            xml_files,
            username,
            config_dict,
            args.path_to_crowdin,
        )

    if crowdin_download.has_created_commits() or _COMMITS_CREATED:
        print("\nDone!")
        sys.exit(0)
    else:
        print("\nNothing to commit")
        sys.exit(2)


if __name__ == "__main__":
    main()
