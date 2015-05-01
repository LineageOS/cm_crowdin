#!/usr/bin/env python
# -*- coding: utf-8 -*-
# crowdin_sync.py
#
# Updates Crowdin source translations and pushes translations
# directly to CyanogenMod's Gerrit.
#
# Copyright (C) 2014-2015 The CyanogenMod Project
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

from __future__ import print_function

import argparse
import git
import os
import subprocess
import sys

from xml.dom import minidom

# ################################ FUNCTIONS ################################# #


def run_subprocess(cmd, silent=False):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True)
    comm = p.communicate()
    exit_code = p.returncode
    if exit_code != 0 and not silent:
        print("There was an error running the subprocess.\n"
              "cmd: %s\n"
              "exit code: %d\n"
              "stdout: %s\n"
              "stderr: %s" % (cmd, exit_code, comm[0], comm[1]),
              file=sys.stderr)
    return comm, exit_code


def push_as_commit(path, name, branch, username):
    print('Committing %s on branch %s' % (name, branch))

    # Get path
    path = os.path.join(os.getcwd(), path)
    if not path.endswith('.git'):
        path = os.path.join(path, '.git')

    # Create repo object
    repo = git.Repo(path)

    # Remove previously deleted files from Git
    files = repo.git.ls_files(d=True).split('\n')
    if files and files[0]:
        repo.git.rm(files)

    # Add all files to commit
    repo.git.add('-A')

    # Create commit; if it fails, probably empty so skipping
    try:
        repo.git.commit(m='Automatic translation import')
    except:
        print('Failed to create commit for %s, probably empty: skipping'
              % name, file=sys.stderr)
        return

    # Push commit
    try:
        repo.git.push('ssh://%s@review.cyanogenmod.org:29418/%s' % (username, name),
                      'HEAD:refs/for/%s%%topic=translation' % branch)
        print('Successfully pushed commit for %s' % name)
    except:
        print('Failed to push commit for %s' % name, file=sys.stderr)


def check_run(cmd):
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    ret = p.wait()
    if ret != 0:
        print('Failed to run cmd: %s' % ' '.join(cmd), file=sys.stderr)
        sys.exit(ret)


def find_xml():
    for dp, dn, file_names in os.walk(os.getcwd()):
        for f in file_names:
            if os.path.splitext(f)[1] == '.xml':
                yield os.path.join(dp, f)

# ############################################################################ #


def parse_args():
    parser = argparse.ArgumentParser(
        description="Synchronising CyanogenMod's translations with Crowdin")
    sync = parser.add_mutually_exclusive_group()
    parser.add_argument('-u', '--username', help='Gerrit username',
                        required=True)
    parser.add_argument('-b', '--branch', help='CyanogenMod branch',
                        required=True)
    sync.add_argument('--no-upload', action='store_true',
                      help='Only download CM translations from Crowdin')
    sync.add_argument('--no-download', action='store_true',
                      help='Only upload CM source translations to Crowdin')
    return parser.parse_args()

# ################################# PREPARE ################################## #


def check_dependencies():
    print('\nSTEP 0: Checking dependencies & define shared variables')

    # Check for Ruby version of crowdin-cli
    cmd = ['gem', 'list', 'crowdin-cli', '-i']
    if run_subprocess(cmd, silent=True)[1] != 0:
        print('You have not installed crowdin-cli.', file=sys.stderr)
        return False
    print('Found: crowdin-cli')

    return True


def load_xml(x='android/default.xml'):
    # Variables regarding android/default.xml
    print('Loading: %s' % x)
    try:
        return minidom.parse(x)
    except IOError:
        print('You have no %s.' % x, file=sys.stderr)
        return None
    except Exception:
        # TODO: minidom should not be used.
        print('Malformed %s.' % x, file=sys.stderr)
        return None


def check_files(branch):
    files = ['crowdin/config.yaml',
             'crowdin/extra_packages_%s.xml' % branch,
             'crowdin/config_aosp.yaml',
             'crowdin/crowdin_%s.yaml' % branch,
             'crowdin/crowdin_%s_aosp.yaml' % branch
             ]
    for f in files:
        if not os.path.isfile(f):
            print('You have no %s.' % f, file=sys.stderr)
            return False
        print('Found: %s' % f)
    return True

# ################################### MAIN ################################### #


def upload_crowdin(branch, no_upload=False):
    print('\nSTEP 1: Upload Crowdin source translations')
    if no_upload:
        print('Skipping source translations upload')
        return
    print('\nUploading Crowdin source translations (AOSP supported languages)')

    # Execute 'crowdin-cli upload sources' and show output
    check_run(['crowdin-cli',
               '--config=crowdin/crowdin_%s.yaml' % branch,
               '--identity=crowdin/config.yaml',
               'upload', 'sources'])

    print('\nUploading Crowdin source translations '
          '(non-AOSP supported languages)')
    # Execute 'crowdin-cli upload sources' and show output
    check_run(['crowdin-cli',
               '--config=crowdin/crowdin_%s_aosp.yaml' % branch,
               '--identity=crowdin/config_aosp.yaml',
               'upload', 'sources'])


def download_crowdin(branch, xml, username, no_download=False):
    print('\nSTEP 2: Download Crowdin translations')
    if no_download:
        print('Skipping translations download')
        return

    print('\nDownloading Crowdin translations (AOSP supported languages)')
    # Execute 'crowdin-cli download' and show output
    check_run(['crowdin-cli',
               '--config=crowdin/crowdin_%s.yaml' % branch,
               '--identity=crowdin/config.yaml',
               'download', '--ignore-match'])

    print('\nDownloading Crowdin translations (non-AOSP supported languages)')
    # Execute 'crowdin-cli download' and show output
    check_run(['crowdin-cli',
               '--config=crowdin/crowdin_%s_aosp.yaml' % branch,
               '--identity=crowdin/config_aosp.yaml',
               'download', '--ignore-match'])

    print('\nSTEP 3: Remove useless empty translations')
    empty_contents = {
        '<resources/>',
        '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>',
        ('<resources xmlns:android='
         '"http://schemas.android.com/apk/res/android"/>'),
        ('<resources xmlns:android="http://schemas.android.com/apk/res/android"'
         ' xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>'),
        ('<resources xmlns:tools="http://schemas.android.com/tools"'
         ' xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>')
    }
    xf = None
    for xml_file in find_xml():
        xf = open(xml_file).read()
        for line in empty_contents:
            if line in xf:
                print('Removing ' + xml_file)
                os.remove(xml_file)
                break
    del xf

    print('\nSTEP 4: Create a list of pushable translations')
    # Get all files that Crowdin pushed
    paths = []
    files = [
        ('crowdin/crowdin_%s.yaml' % branch, 'crowdin/config.yaml'),
        ('crowdin/crowdin_%s_aosp.yaml' % branch, 'crowdin/config_aosp.yaml')
    ]
    for c, i in files:
        cmd = ['crowdin-cli', '--config=%s' % c, '--identity=%s' % i,
               'list', 'sources']
        comm, ret = run_subprocess(cmd)
        if ret != 0:
            sys.exit(ret)
        for p in str(comm[0]).split("\n"):
            paths.append(p.replace('/%s' % branch, ''))

    print('\nSTEP 5: Upload to Gerrit')
    items = [x for sub in xml for x in sub.getElementsByTagName('project')]
    all_projects = []

    for path in paths:
        path = path.strip()
        if not path:
            continue

        if "/res" not in path:
            print('WARNING: Cannot determine project root dir of '
                  '[%s], skipping.' % path)
            continue
        result = path.split('/res')[0].strip('/')
        if result == path.strip('/'):
            print('WARNING: Cannot determine project root dir of '
                  '[%s], skipping.' % path)
            continue

        if result in all_projects:
            continue

        # When a project has multiple translatable files, Crowdin will
        # give duplicates.
        # We don't want that (useless empty commits), so we save each
        # project in all_projects and check if it's already in there.
        all_projects.append(result)

        # Search android/default.xml or crowdin/extra_packages_%(branch).xml
        # for the project's name
        for project in items:
            if project.attributes['path'].value != result:
                continue

            br = project.getAttribute('revision') or branch

            push_as_commit(result, project.getAttribute('name'), br, username)
            break


def main():
    if not check_dependencies():
        sys.exit(1)

    args = parse_args()
    default_branch = args.branch

    print('Welcome to the CM Crowdin sync script!')

    xml_android = load_xml()
    if xml_android is None:
        sys.exit(1)

    xml_extra = load_xml(x='crowdin/extra_packages_%s.xml' % default_branch)
    if xml_extra is None:
        sys.exit(1)

    if not check_files(default_branch):
        sys.exit(1)

    upload_crowdin(default_branch, args.no_upload)
    download_crowdin(default_branch, (xml_android, xml_extra),
                     args.username, args.no_download)
    print('\nDone!')

if __name__ == '__main__':
    main()
