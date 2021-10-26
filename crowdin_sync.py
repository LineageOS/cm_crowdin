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
import git
import os
import re
import shutil
import sys
import time
import threading

from lxml import etree
from signal import signal, SIGINT
from subprocess import Popen, PIPE

# ################################# GLOBALS ################################## #

_DIR = os.path.dirname(os.path.realpath(__file__))
_COMMITS_CREATED = False
_DONE = False


# ################################ FUNCTIONS ################################# #


def run_subprocess(cmd, silent=False, spinner=False):
    global _DONE
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    if spinner:
        _DONE = False
        t = threading.Thread(target=spin_cursor)
        t.start()

    comm = p.communicate()
    exit_code = p.returncode
    _DONE = True
    if exit_code != 0 and not silent:
        print("There was an error running the subprocess.\n"
              "cmd: %s\n"
              "exit code: %d\n"
              "stdout: %s\n"
              "stderr: %s" % (cmd, exit_code, comm[0], comm[1]),
              file=sys.stderr)
    return comm, exit_code


def spin_cursor():
    spinner = itertools.cycle([".", "..", "...", "....", "....."])
    while not _DONE:
        sys.stdout.write("\x1b[1K\r")
        output = next(spinner)
        remove = len(output)
        sys.stdout.write(output)
        sys.stdout.flush()
        time.sleep(0.5)
    sys.stdout.write("\x1b[1K\r")


def add_target_paths(extracted_files, repo, base_path, project_path):
    # Add or remove the files extracted by the download command to the commit
    count = 0

    # Strip all comments
    for f in extracted_files:
        if f.startswith(project_path):
            clean_xml_file(base_path, f, repo)

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


def clean_xml_file(base_path, filename, repo):
    path = os.path.join(base_path, filename)

    # We don't want to create every file, just work with those already existing
    if not os.path.isfile(path):
        print(f"Called clean_xml_file, but not a file: {path}")
        return

    try:
        fh = open(path, 'r+')
    except OSError:
        print(f'\nSomething went wrong while opening file {path}')
        return

    XML = fh.read()
    content = ''

    # Take the original xml declaration and prepend it
    declaration = XML.split('\n')[0]
    if '<?' in declaration:
        content = declaration + '\n'
        XML = XML[XML.find('\n')+1:]

    try:
        tree = etree.fromstring(XML)
    except etree.XMLSyntaxError as err:
        print(f'{filename}: XML Error: {err.error_log}')
        filename, ext = os.path.splitext(path)
        if ext == '.xml':
            reset_file(path, repo)
        return

    # Remove strings with 'product=*' attribute but no 'product=default'
    # This will ensure aapt2 will not throw an error when building these
    alreadyRemoved = []
    productStrings = tree.xpath("//string[@product]")
    for ps in productStrings:
        # if we already removed the items, don't process them
        if ps in alreadyRemoved:
            continue
        stringName = ps.get('name')
        stringsWithSameName = tree.xpath("//string[@name='{0}']"
                                         .format(stringName))

        # We want to find strings with product='default' or no product attribute at all
        hasProductDefault = False
        for string in stringsWithSameName:
            product = string.get('product')
            if product is None or product == 'default':
                hasProductDefault = True
                break

        # Every occurance of the string has to be removed when no string with the same name and
        # 'product=default' (or no product attribute) was found
        if not hasProductDefault:
            print(f"\n{path}: Found string '{stringName}' with missing 'product=default' attribute",
                  end='')
            for string in stringsWithSameName:
                tree.remove(string)
                alreadyRemoved.append(string)

    header = ''
    comments = tree.xpath('//comment()')
    for c in comments:
        p = c.getparent()
        if p is None:
            # Keep all comments in header
            header += str(c).replace('\\n', '\n').replace('\\t', '\t') + '\n'
            continue
        p.remove(c)

    # Take the original xml declaration and prepend it
    declaration = XML.split('\n')[0]
    if '<?' in declaration:
        content = declaration + '\n'

    content += etree.tostring(tree, pretty_print=True, encoding="unicode", xml_declaration=False)

    if header != '':
        content = content.replace('?>\n', '?>\n' + header)

    # Sometimes spaces are added, we don't want them
    content = re.sub("[ ]*<\/resources>", "</resources>", content)

    # Overwrite file with content stripped by all comments
    fh.seek(0)
    fh.write(content)
    fh.truncate()
    fh.close()

    # Remove files which don't have any translated strings
    contentList = list(tree)
    if len(contentList) == 0:
        print(f'\nRemoving {path}')
        os.remove(path)
        # If that was the last file in the folder, we need to remove the folder as well
        dir_name = os.path.dirname(path)
        if os.path.isdir(dir_name):
            if not os.listdir(dir_name):
                print(f"Removing {dir_name}")
                os.rmdir(dir_name)


# For files we can't process due to errors, create a backup
# and checkout the file to get it back to the previous state
def reset_file(filepath, repo):
    backupFile = None
    parts = filepath.split("/")
    found = False
    for s in parts:
        curPart = s
        if not found and s.startswith("res"):
            curPart = s + "_backup"
            found = True
        if backupFile is None:
            backupFile = curPart
        else:
            backupFile = backupFile + '/' + curPart

    path, filename = os.path.split(backupFile)
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(backupFile):
        i = 1
        while os.path.exists(backupFile + str(i)):
            i+=1
        backupFile = backupFile + str(i)
    shutil.copy(filepath, backupFile)
    repo.git.checkout(filepath)


def push_as_commit(extracted_files, base_path, project_path, project_name, branch, username):
    global _COMMITS_CREATED
    print(f'\nCommitting {project_name} on branch {branch}: ', end='')

    # Get path
    path = os.path.join(base_path, project_path)
    if not path.endswith('.git'):
        path = os.path.join(path, '.git')

    # Create repo object
    repo = git.Repo(path)

    # Add all files to commit
    count = add_target_paths(extracted_files, repo, base_path, project_path)

    if count == 0:
        print('Nothing to commit')
        return

    # Create commit; if it fails, probably empty so skipping
    try:
        repo.git.commit(m='Automatic translation import')
    except:
        print('Failed to commit, probably empty: skipping', file=sys.stderr)
        return

    # Push commit
    try:
        repo.git.push(f'ssh://{username}@review.lineageos.org:29418/{project_name}',
                      f'HEAD:refs/for/{branch}%topic=translation')
        print('Success')
    except Exception as e:
        print(e, '\nFailed to push!', file=sys.stderr)
        return

    _COMMITS_CREATED = True


def submit_gerrit(branch, username, owner):
    # If an owner is specified, modify the query so we only get the ones wanted
    ownerArg = ''
    if owner is not None:
        ownerArg = f'owner:{owner}'

    # Find all open translation changes
    cmd = ['ssh', '-p', '29418',
        f'{username}@review.lineageos.org',
        'gerrit', 'query',
        'status:open',
        f'branch:{branch}',
        ownerArg,
        'message:"Automatic translation import"',
        'topic:translation',
        '--current-patch-set',
        '--format=JSON']
    commits = 0
    msg, code = run_subprocess(cmd)
    if code != 0:
        print(f'Failed: {msg[1]}')
        return

    # Each line is one valid JSON object, except the last one, which is empty
    for line in msg[0].strip('\n').split('\n'):
        js = json.loads(line)
        # We get valid JSON, but not every result line is one we want
        if not 'currentPatchSet' in js or not 'revision' in js['currentPatchSet']:
            continue
        # Add Code-Review +2 and Verified+1 labels and submit
        cmd = ['ssh', '-p', '29418',
        f'{username}@review.lineageos.org',
        'gerrit', 'review',
        '--verified +1',
        '--code-review +2',
        '--submit', js['currentPatchSet']['revision']]
        msg, code = run_subprocess(cmd, True)
        print('Submitting commit %s: ' % js['url'], end='')
        if code != 0:
            errorText = msg[1].replace('\n\n', '; ').replace('\n', '')
            print(f'Failed: {errorText}')
        else:
            print('Success')

        commits += 1

    if commits == 0:
        print("Nothing to submit!")
        return


def check_run(cmd):
    p = Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    ret = p.wait()
    if ret != 0:
        joined = ' '.join(cmd)
        print(f'Failed to run cmd: {joined}', file=sys.stderr)
        sys.exit(ret)


def find_xml(base_path):
    for dp, dn, file_names in os.walk(base_path):
        for f in file_names:
            if os.path.splitext(f)[1] == '.xml':
                yield os.path.join(dp, f)

# ############################################################################ #


def parse_args():
    parser = argparse.ArgumentParser(
        description="Synchronising LineageOS' translations with Crowdin")
    parser.add_argument('-u', '--username', help='Gerrit username')
    parser.add_argument('-b', '--branch', help='LineageOS branch',
                        required=True)
    parser.add_argument('-c', '--config', help='Custom yaml config')
    parser.add_argument('--upload-sources', action='store_true',
                        help='Upload sources to Crowdin')
    parser.add_argument('--upload-translations', action='store_true',
                        help='Upload translations to Crowdin')
    parser.add_argument('--download', action='store_true',
                        help='Download translations from Crowdin')
    parser.add_argument('-s', '--submit', action='store_true',
                        help='Merge open translation commits')
    parser.add_argument('-o', '--owner',
                        help='Specify the owner of the commits to submit')
    parser.add_argument('-p', '--path-to-crowdin',
                        help='Path to crowdin executable (will look in PATH by default)',
                        default='crowdin')
    return parser.parse_args()

# ################################# PREPARE ################################## #


def check_dependencies():
    # Check for Java version of crowdin
    cmd = ['which', 'crowdin']
    if run_subprocess(cmd, silent=True)[1] != 0:
        print('You have not installed crowdin.', file=sys.stderr)
        return False
    return True


def load_xml(x):
    try:
        return etree.parse(x)
    except etree.XMLSyntaxError:
        print(f'Malformed {x}', file=sys.stderr)
        return None
    except Exception:
        print(f'You have no {x}', file=sys.stderr)
        return None


def check_files(files):
    for f in files:
        if not os.path.isfile(f):
            print(f'You have no {f}.', file=sys.stderr)
            return False
    return True


# ################################### MAIN ################################### #

def upload_sources_crowdin(branch, config_dict, crowdin_path):
    global _COMMITS_CREATED
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nUploading sources to Crowdin ({config_dict['headers'][i]})")
        cmd = [
            crowdin_path,
            'upload', 'sources', f'--branch={branch}',
            f'--config={cfg}',
        ]
        comm, ret = run_subprocess(cmd, spinner=True)
        if ret != 0:
            print(f"Failed to upload:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)
    _COMMITS_CREATED = True


def upload_translations_crowdin(branch, config_dict, crowdin_path):
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nUploading translations to Crowdin ({config_dict['headers'][i]})")
        cmd = [
            crowdin_path,
            'upload', 'translations', f'--branch={branch}',
            '--no-import-duplicates', '--import-eq-suggestions',
            '--auto-approve-imported',
            f'--config={cfg}',
        ]
        comm, ret = run_subprocess(cmd, spinner=True)
        if ret != 0:
            print(f"Failed to upload:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)


def download_crowdin(base_path, branch, xml, username, config_dict, crowdin_path):
    extracted = []
    for i, cfg in enumerate(config_dict["files"]):
        print(f"\nDownloading translations from Crowdin ({config_dict['headers'][i]})")
        cmd = [crowdin_path, "download", f"--branch={branch}", f"--config={cfg}"]
        comm, ret = run_subprocess(cmd, spinner=True)
        if ret != 0:
            print(f"Failed to download:\n{comm[1]}", file=sys.stderr)
            sys.exit(1)
        extracted += get_extracted_files(comm[0], branch)

    upload_translations_gerrit(extracted, xml, base_path, branch, username)


def upload_translations_gerrit(extracted, xml, base_path, branch, username):
    print("\nUploading translations to Gerrit")
    items = [x for xmlfile in xml for x in xmlfile.findall("//project")]
    all_projects = []

    for path in extracted:
        path = path.strip()
        if not path:
            continue

        if "/res" not in path:
            print(f'WARNING: Cannot determine project root dir of [{path}], skipping.')
            continue

        # Usually the project root is everything before /res
        # but there are special cases where /res is part of the repo name as well
        parts = path.split("/res")
        if len(parts) == 2:
            project_path = parts[0]
        elif len(parts) == 3:
            project_path = parts[0] + "/res" + parts[1]
        else:
            print(f'WARNING: Splitting the path not successful for [{path}], skipping')
            continue

        project_path = project_path.strip("/")
        if project_path == path.strip("/"):
            print(f"WARNING: Cannot determine project root dir of [{path}], skipping.")
            continue

        if project_path in all_projects:
            continue

        # When a project has multiple translatable files, Crowdin will
        # give duplicates.
        # We don't want that (useless empty commits), so we save each
        # project in all_projects and check if it's already in there.
        all_projects.append(project_path)

        # Search android/default.xml or config/%(branch)_extra_packages.xml
        # for the project's name
        result_path = None
        result_project = None
        for project in items:
            path = project.get("path")
            if not (project_path + "/").startswith(path + "/"):
                continue
            # We want the longest match, so projects in subfolders of other projects are also
            # taken into account
            if result_path is None or len(path) > len(result_path):
                result_path = path
                result_project = project

        # Just in case no project was found
        if result_path is None:
            continue

        if project_path != result_path:
            if result_path in all_projects:
                continue
            project_path = result_path
            all_projects.append(project_path)

        branch = result_project.get("revision") or branch
        project_name = result_project.get("name")

        push_as_commit(extracted, base_path, project_path,
                       project_name, branch, username)


def get_extracted_files(comm, branch):
    # Get all files that Crowdin pushed
    # We need to manually parse the shell output
    extracted = []
    for p in comm.split("\n"):
        if "Extracted" in p:
            path = re.sub(".*Extracted:\s*", "", p)
            path = path.replace("'", "").replace(f"/{branch}", "")
            extracted.append(path)
    return extracted


def sig_handler(signal_received, frame):
    global _DONE
    print('')
    print('SIGINT or CTRL-C detected. Exiting gracefully')
    _DONE = True
    exit(0)


def main():
    global _COMMITS_CREATED
    signal(SIGINT, sig_handler)
    args = parse_args()
    default_branch = args.branch

    if args.submit:
        if args.username is None:
            print('Argument -u/--username is required for submitting!')
            sys.exit(1)
        submit_gerrit(default_branch, args.username, args.owner)
        sys.exit(0)

    base_path_branch_suffix = default_branch.replace('-', '_').replace('.', '_').upper()
    base_path_env = f'LINEAGE_CROWDIN_BASE_PATH_{base_path_branch_suffix}'
    base_path = os.getenv(base_path_env)
    if base_path is None:
        cwd = os.getcwd()
        print(f'You have not set {base_path_env}. Defaulting to {cwd}')
        base_path = cwd
    if not os.path.isdir(base_path):
        print(f'{base_path_env} is not a real directory: {base_path}')
        sys.exit(1)

    if args.path_to_crowdin == 'crowdin' and not check_dependencies():
        sys.exit(1)

    xml_android = load_xml(x=f'{base_path}/android/default.xml')
    if xml_android is None:
        sys.exit(1)

    xml_extra = load_xml(x=f'{_DIR}/config/{default_branch}_extra_packages.xml')
    if xml_extra is None:
        sys.exit(1)

    xml_snippet = load_xml(x=f'{base_path}/android/snippets/lineage.xml')
    if xml_snippet is None:
        xml_snippet = load_xml(x=f'{base_path}/android/snippets/cm.xml')
    if xml_snippet is None:
        xml_snippet = load_xml(x=f'{base_path}/android/snippets/hal_cm_all.xml')
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
            "non-AOSP supported languages"
        ]
        config_dict["files"] = [
            f"{_DIR}/config/{default_branch}.yaml",
            f"{_DIR}/config/{default_branch}_aosp.yaml"
        ]
    if not check_files(config_dict["files"]):
        sys.exit(1)

    if args.download and args.username is None:
        print('Argument -u/--username is required for translations download')
        sys.exit(1)

    if args.upload_sources:
        upload_sources_crowdin(default_branch, config_dict, args.path_to_crowdin)
    if args.upload_translations:
        upload_translations_crowdin(default_branch, config_dict, args.path_to_crowdin)
    if args.download:
        download_crowdin(base_path, default_branch, xml_files,
                         args.username, config_dict, args.path_to_crowdin)

    if _COMMITS_CREATED:
        print('\nDone!')
        sys.exit(0)
    else:
        print('\nNothing to commit')
        sys.exit(2)

if __name__ == '__main__':
    main()
