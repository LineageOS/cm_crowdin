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

from collections import defaultdict
from lxml import etree

import utils

_COMMITS_CREATED = False


def download_crowdin(base_path, branch, xml, username, config_dict, crowdin_path):
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
        extracted.extend(comm[0].split())

    upload_translations_gerrit(extracted, xml, base_path, branch, username)


def upload_translations_gerrit(extracted, xml, base_path, branch, username):
    print("\nUploading translations to Gerrit")
    projects = [x for xml_file in xml for x in xml_file.findall("//project")]

    all_projects = set()
    projects_to_push = defaultdict(list)
    project_infos = {}

    for project in projects:
        path = project.get("path")
        name = project.get("name")
        if path and name:
            project_infos[path.strip("/")] = {
                "name": name,
                "revision": project.get("revision") or branch,
            }

    for file_path in extracted:
        file_path = file_path.strip()
        if not file_path:
            continue

        best_match_path = None

        for xml_path in project_infos:
            if (file_path.strip("/") + "/").startswith(xml_path + "/"):
                if best_match_path is None or len(xml_path) > len(best_match_path):
                    best_match_path = xml_path

        if best_match_path:
            projects_to_push[best_match_path].append(file_path)
        else:
            print(
                f"WARNING: Could not find a matching project in XML for file: [{file_path}], skipping."
            )

    # We now push all found projects one by one
    for project_path, files_in_project in projects_to_push.items():
        project_info = project_infos[project_path]
        project_name = project_info["name"]
        project_branch = project_info["revision"]

        print(
            f"Processing project: {project_name} (path: {project_path}) with {len(files_in_project)} files."
        )
        push_as_commit(
            files_in_project,
            base_path,
            project_path,
            project_name,
            project_branch,
            username,
        )


def push_as_commit(
    extracted_files, base_path, project_path, project_name, branch, username
):
    global _COMMITS_CREATED
    print(f"\nCommitting {project_name} on branch {branch}: ")

    # Get path
    path = os.path.join(base_path, project_path)
    if not path.endswith(".git"):
        path = os.path.join(str(path), ".git")

    # Create repo object
    repo = git.Repo(str(path))

    # Strip all comments, find incomplete product strings and remove empty files
    for f in extracted_files:
        clean_xml_file(os.path.join(base_path, f), repo)

    # Add all files to commit
    count = add_to_commit(extracted_files, repo, project_path)
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

    # Remove strings with no content
    empty_strings = root.xpath("//string[not(text())]")
    for element in empty_strings:
        print(f"Found an empty string in {path}")
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


def add_to_commit(extracted_files, repo, project_path):
    # Add or remove the files extracted by the download command to the commit
    count = 0

    # Modified and untracked files
    modified = repo.git.ls_files(m=True, o=True)
    for m in modified.split("\n"):
        path = os.path.join(project_path, m)
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
