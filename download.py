#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# download.py
#
# Helper script for downloading translation source and
# uploading it to LineageOS' gerrit
#
# Copyright (C) 2014-2016 The CyanogenMod Project
# Copyright (C) 2017-2025 The LineageOS Project
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

import git
import os
import re
import shutil
import sys

from lxml import etree

import utils

_COMMITS_CREATED = False


def download_crowdin(base_path, branch, username, config_dict, crowdin_path):
    extracted = []
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nDownloading translations from Crowdin ({config_dict['headers'][i]})")
        cmd = [
            crowdin_path,
            "download",
            f"--branch={branch}",
            f"--config={cfg}",
            "--plain",
        ]
        comm, ret = utils.run_subprocess(cmd, show_spinner=True)
        if ret != 0:
            print(f"Failed to download:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)
        extracted = comm[0].split()

    upload_translations_gerrit(extracted, base_path, username)


def upload_translations_gerrit(extracted, base_path, username):
    print("\nUploading translations to Gerrit")
    project_infos = {}

    for path in extracted:
        path = path.strip()
        if not path:
            continue

        full_path = os.path.join(base_path, path)
        if not os.path.exists(full_path):
            continue

        project_info = get_project_info(full_path)
        if project_info:
            if project_info["project_name"] not in project_infos:
                project_infos[project_info["project_name"]] = project_info

    for project_name, info in project_infos.items():
        push_as_commit(
            extracted,
            base_path,
            info["project_path"],
            project_name,
            info["project_branch"],
            username,
        )


def get_project_info(full_path):
    cmd = ["repo", "info", full_path]
    comm, ret = utils.run_subprocess(cmd, show_spinner=False)
    if ret != 0:
        print(
            f"Failed to determine project root dir of [{full_path}]:\n{comm[1]}",
            file=sys.stderr,
        )
        return None

    data = {}
    for line in comm[0].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()

    required_keys = ["Project", "Manifest revision", "Mount path"]
    if not all(key in data for key in required_keys):
        print(f"WARNING: Cannot determine project root dir of [{full_path}], skipping.")
        return None

    return {
        "project_name": data["Project"],
        "project_branch": data["Manifest revision"].replace("refs/heads/", ""),
        "project_path": data["Mount path"],
    }


def push_as_commit(
    extracted_files, base_path, project_path, project_name, branch, username
):
    global _COMMITS_CREATED
    print(f"\nCommitting {project_name} on branch {branch}: ")

    # Get path
    path = project_path
    if not path.endswith(".git"):
        path = os.path.join(path, ".git")

    # Create repo object
    repo = git.Repo(path)

    project_path_relative = os.path.relpath(project_path, base_path)
    # Strip all comments, find incomplete product strings and remove empty files
    for f in extracted_files:
        if f.startswith(project_path_relative):
            clean_xml_file(os.path.join(base_path, f), repo)

    # Add all files to commit
    count = add_to_commit(extracted_files, repo, base_path, project_path)
    if count == 0:
        print("Nothing to commit")
        return

    # Create commit; if it fails, probably empty so skipping
    try:
        repo.git.commit(m="Automatic translation import")
    except Exception as e:
        print(e, "Failed to commit, probably empty: skipping", file=sys.stderr)
        return

    # Push commit
    try:
        repo.git.push(
            f"ssh://{username}@review.lineageos.org:29418/{project_name}",
            f"HEAD:refs/for/{branch}%topic=translation",
        )
        print("Successfully pushed!")
    except Exception as e:
        print(e, "Failed to push!", file=sys.stderr)
        return

    _COMMITS_CREATED = True


def clean_xml_file(path, repo):
    # We don't want to create every file, just work with those already existing
    if not os.path.isfile(path):
        print(f"Called clean_xml_file, but not a file: {path}")
        return

    print(f"Cleaning file {path}")

    try:
        parser = etree.XMLParser(strip_cdata=False)
        tree = etree.parse(path, parser=parser)
        root = tree.getroot()
    except etree.XMLSyntaxError as err:
        print(f"{path}: XML Error: {err}")
        filename, ext = os.path.splitext(path)
        if ext == ".xml":
            reset_file(path, repo)
        return
    except OSError as err:
        print(f"Something went wrong while opening/parsing file {path}: {err}")
        return

    # Remove strings with 'product' attribute but no 'product=default' or without 'product'
    already_removed = set()
    product_strings = root.xpath("//string[@product]")
    for ps in product_strings:
        if ps in already_removed:
            continue
        string_name = ps.get("name")
        matching_strings = root.xpath(f"//string[@name='{string_name}']")
        has_default = any(
            s.get("product") in (None, "default") for s in matching_strings
        )
        if not has_default:
            print(
                f"{path}: Found string '{string_name}' with missing 'product=default' attribute"
            )
            for string in matching_strings:
                root.remove(string)
                already_removed.add(string)

    # Extract header comments and remove all other comments
    header_comment = root.xpath("/resources/preceding-sibling::comment()")
    other_comments = root.xpath("/resources/comment()")
    for comment in other_comments:
        root.remove(comment)

    # Remove non-translatable string(-array)s
    non_translatable = root.xpath('//*[@translatable="false"]')
    for element in non_translatable:
        root.remove(element)

    # Generate the XML content
    xml_declaration = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        if "<?xml" in open(path, "r").readline()
        else ""
    )
    content = xml_declaration
    header_str = "".join(
        str(c).replace("\\n", "\n").replace("\\t", "\t") + "\n" for c in header_comment
    )
    content += header_str
    content += etree.tostring(
        root, pretty_print=True, encoding="unicode", xml_declaration=False
    )

    # Remove extra spaces before </resources>
    content = re.sub(r"[ ]*</resources>", r"</resources>", content)

    # Overwrite the file
    try:
        with open(path, "w") as fh:
            fh.write(content)
    except OSError as err:
        print(f"Something went wrong while writing to file {path}: {err}")
        return

    # Remove empty files and their parent directories
    if not list(root):
        print(f"Removing empty content file: {path}")
        os.remove(path)
        dir_name = os.path.dirname(path)
        if os.path.isdir(dir_name) and not os.listdir(dir_name):
            print(f"Removing empty directory: {dir_name}")
            try:
                os.rmdir(dir_name)
            except OSError as e:
                print(f"Error removing directory {dir_name}: {e}")


def add_to_commit(extracted_files, repo, base_path, project_path):
    # Add or remove the files extracted by the download command to the commit
    count = 0

    # Modified and untracked files
    modified = repo.git.ls_files(m=True, o=True)
    for m in modified.split("\n"):
        path = os.path.join(project_path, m)
        path = os.path.relpath(str(path), base_path)
        if path in extracted_files:
            repo.git.add(m)
            count += 1

    deleted = repo.git.ls_files(d=True)
    for d in deleted.split("\n"):
        path = os.path.join(project_path, d)
        if path in extracted_files:
            repo.git.rm(d)
            count += 1

    return count


# For files which we can't process due to errors, create a backup
# and checkout the file to get it back to the previous state
def reset_file(filepath, repo):
    backup_file = None
    parts = filepath.split("/")
    found = False
    for s in parts:
        current_part = s
        if not found and s.startswith("res"):
            current_part = s + "_backup"
            found = True
        if backup_file is None:
            backup_file = current_part
        else:
            backup_file = backup_file + "/" + current_part

    path, filename = os.path.split(backup_file)
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(backup_file):
        i = 1
        while os.path.exists(backup_file + str(i)):
            i += 1
        backup_file = backup_file + str(i)
    shutil.copy(filepath, backup_file)
    repo.git.checkout(filepath)


def has_created_commits():
    return _COMMITS_CREATED
