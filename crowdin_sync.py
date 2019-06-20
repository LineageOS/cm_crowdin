#!/usr/bin/env python
# -*- coding: utf-8 -*-
# crowdin_sync.py
#
# Updates Crowdin source translations and pushes translations
# directly to LineageOS' Gerrit.
#
# Copyright (C) 2014-2016 The CyanogenMod Project
# Copyright (C) 2017-2019 The LineageOS Project
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
import json
import git
import os
import re
import subprocess
import sys
import yaml

from lxml import etree
from xml.dom import minidom

# ################################# GLOBALS ################################## #

_DIR = os.path.dirname(os.path.realpath(__file__))
_COMMITS_CREATED = False

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


def add_target_paths(config_files, repo, base_path, project_path):
    # Add or remove the files given in the config files to the commit
    count = 0
    file_paths = []
    for f in config_files:
        fh = open(f, "r")
        try:
            config = yaml.load(fh)
            for tf in config['files']:
                if project_path in tf['source']:
                    target_path = tf['translation']
                    lang_codes = tf['languages_mapping']['android_code']
                    for l in lang_codes:
                        lpath = get_target_path(tf['translation'], tf['source'],
                            lang_codes[l], project_path)
                        file_paths.append(lpath)
        except yaml.YAMLError as e:
            print(e, '\n Could not parse YAML.')
            exit()
        fh.close()

    # Strip all comments
    for f in file_paths:
        clean_file(base_path, project_path, f)

    # Modified and untracked files
    modified = repo.git.ls_files(m=True, o=True)
    for m in modified.split('\n'):
        if m in file_paths:
            repo.git.add(m)
            count += 1

    deleted = repo.git.ls_files(d=True)
    for d in deleted.split('\n'):
        if d in file_paths:
            repo.git.rm(d)
            count += 1

    return count


def split_path(path):
    # Split the given string to path and filename
    if '/' in path:
        original_file_name = path[1:][path.rfind("/"):]
        original_path = path[:path.rfind("/")]
    else:
        original_file_name = path
        original_path = ''

    return original_path, original_file_name


def get_target_path(pattern, source, lang, project_path):
    # Make strings like '/%original_path%-%android_code%/%original_file_name%' valid file paths
    # based on the source string's path
    original_path, original_file_name = split_path(source)

    target_path = pattern #.lstrip('/')
    target_path = target_path.replace('%original_path%', original_path)
    target_path = target_path.replace('%android_code%', lang)
    target_path = target_path.replace('%original_file_name%', original_file_name)
    target_path = target_path.replace(project_path, '')
    target_path = target_path.lstrip('/')
    return target_path


def clean_file(base_path, project_path, filename):
    path = base_path + '/' + project_path + '/' + filename

    # We don't want to create every file, just work with those already existing
    if not os.path.isfile(path):
        return

    try:
        fh = open(path, 'r+')
    except:
        print('Something went wrong while opening file %s' % (path))
        return

    XML = fh.read()
    tree = etree.fromstring(XML)

    header = ''
    comments = tree.xpath('//comment()')
    for c in comments:
        p = c.getparent()
        if p is None:
            # Keep all comments in header
            header += str(c).replace('\\n', '\n').replace('\\t', '\t') + '\n'
            continue
        p.remove(c)

    content = ''

    # Take the original xml declaration and prepend it
    declaration = XML.split('\n')[0]
    if '<?' in declaration:
        content = declaration + '\n'

    content += etree.tostring(tree, pretty_print=True, encoding="utf-8", xml_declaration=False)

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
    empty_contents = {
        '<resources/>',
        '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>',
        ('<resources xmlns:android='
         '"http://schemas.android.com/apk/res/android"/>'),
        ('<resources xmlns:android="http://schemas.android.com/apk/res/android"'
         ' xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>'),
        ('<resources xmlns:tools="http://schemas.android.com/tools"'
         ' xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>'),
        '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n</resources>',
        '<resources>\n</resources>'
    }
    for line in empty_contents:
        if line in content:
            print('Removing ' + path)
            os.remove(path)
            break

def push_as_commit(config_files, base_path, path, name, branch, username):
    print('Committing %s on branch %s' % (name, branch))

    # Get path
    project_path = path
    path = os.path.join(base_path, path)
    if not path.endswith('.git'):
        path = os.path.join(path, '.git')

    # Create repo object
    repo = git.Repo(path)

    # Add all files to commit
    count = add_target_paths(config_files, repo, base_path, project_path)

    if count == 0:
        print('Nothing to commit')
        return

    # Create commit; if it fails, probably empty so skipping
    try:
        repo.git.commit(m='Automatic translation import')
    except:
        print('Failed to create commit for %s, probably empty: skipping'
              % name, file=sys.stderr)
        return

    # Push commit
    try:
        repo.git.push('ssh://%s@review.lineageos.org:29418/%s' % (username, name),
                      'HEAD:refs/for/%s%%topic=translation' % branch)
        print('Successfully pushed commit for %s' % name)
    except:
        print('Failed to push commit for %s' % name, file=sys.stderr)

    _COMMITS_CREATED = True


def submit_gerrit(branch, username):
    # Find all open translation changes
    cmd = ['ssh', '-p', '29418',
        '{}@review.lineageos.org'.format(username),
        'gerrit', 'query',
        'status:open',
        'branch:{}'.format(branch),
        'message:"Automatic translation import"',
        'topic:translation',
        '--current-patch-set',
        '--format=JSON']
    commits = 0
    msg, code = run_subprocess(cmd)
    if code != 0:
        print('Failed: {0}'.format(msg[1]))
        return

    # Each line is one valid JSON object, except the last one, which is empty
    for line in msg[0].strip('\n').split('\n'):
        js = json.loads(line)
        # We get valid JSON, but not every result line is one we want
        if not 'currentPatchSet' in js or not 'revision' in js['currentPatchSet']:
            continue
        # Add Code-Review +2 and Verified+1 labels and submit
        cmd = ['ssh', '-p', '29418',
        '{}@review.lineageos.org'.format(username),
        'gerrit', 'review',
        '--verified +1',
        '--code-review +2',
        '--submit', js['currentPatchSet']['revision']]
        msg, code = run_subprocess(cmd, True)
        if code != 0:
            errorText = msg[1].replace('\n\n', '; ').replace('\n', '')
            print('Submitting commit {0} failed: {1}'.format(js['url'], errorText))
        else:
            print('Success when submitting commit {0}'.format(js['url']))

        commits += 1

    if commits == 0:
        print("Nothing to submit!")
        return


def check_run(cmd):
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    ret = p.wait()
    if ret != 0:
        print('Failed to run cmd: %s' % ' '.join(cmd), file=sys.stderr)
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
    return parser.parse_args()

# ################################# PREPARE ################################## #


def check_dependencies():
    # Check for Java version of crowdin
    cmd = ['dpkg-query', '-W', 'crowdin']
    if run_subprocess(cmd, silent=True)[1] != 0:
        print('You have not installed crowdin.', file=sys.stderr)
        return False
    return True


def load_xml(x):
    try:
        return minidom.parse(x)
    except IOError:
        print('You have no %s.' % x, file=sys.stderr)
        return None
    except Exception:
        # TODO: minidom should not be used.
        print('Malformed %s.' % x, file=sys.stderr)
        return None


def check_files(files):
    for f in files:
        if not os.path.isfile(f):
            print('You have no %s.' % f, file=sys.stderr)
            return False
    return True

# ################################### MAIN ################################### #


def upload_sources_crowdin(branch, config):
    if config:
        print('\nUploading sources to Crowdin (custom config)')
        check_run(['crowdin',
                   '--config=%s/config/%s' % (_DIR, config),
                   'upload', 'sources', '--branch=%s' % branch])
    else:
        print('\nUploading sources to Crowdin (AOSP supported languages)')
        check_run(['crowdin',
                   '--config=%s/config/%s.yaml' % (_DIR, branch),
                   'upload', 'sources', '--branch=%s' % branch])

        print('\nUploading sources to Crowdin (non-AOSP supported languages)')
        check_run(['crowdin',
                   '--config=%s/config/%s_aosp.yaml' % (_DIR, branch),
                   'upload', 'sources', '--branch=%s' % branch])


def upload_translations_crowdin(branch, config):
    if config:
        print('\nUploading translations to Crowdin (custom config)')
        check_run(['crowdin',
                   '--config=%s/config/%s' % (_DIR, config),
                   'upload', 'translations', '--branch=%s' % branch,
                   '--no-import-duplicates', '--import-eq-suggestions',
                   '--auto-approve-imported'])
    else:
        print('\nUploading translations to Crowdin '
              '(AOSP supported languages)')
        check_run(['crowdin',
                   '--config=%s/config/%s.yaml' % (_DIR, branch),
                   'upload', 'translations', '--branch=%s' % branch,
                   '--no-import-duplicates', '--import-eq-suggestions',
                   '--auto-approve-imported'])

        print('\nUploading translations to Crowdin '
              '(non-AOSP supported languages)')
        check_run(['crowdin',
                   '--config=%s/config/%s_aosp.yaml' % (_DIR, branch),
                   'upload', 'translations', '--branch=%s' % branch,
                   '--no-import-duplicates', '--import-eq-suggestions',
                   '--auto-approve-imported'])


def download_crowdin(base_path, branch, xml, username, config):
    if config:
        print('\nDownloading translations from Crowdin (custom config)')
        check_run(['crowdin',
                   '--config=%s/config/%s' % (_DIR, config),
                   'download', '--branch=%s' % branch])
    else:
        print('\nDownloading translations from Crowdin '
              '(AOSP supported languages)')
        check_run(['crowdin',
                   '--config=%s/config/%s.yaml' % (_DIR, branch),
                   'download', '--branch=%s' % branch])

        print('\nDownloading translations from Crowdin '
              '(non-AOSP supported languages)')
        check_run(['crowdin',
                   '--config=%s/config/%s_aosp.yaml' % (_DIR, branch),
                   'download', '--branch=%s' % branch])

    print('\nCreating a list of pushable translations')
    # Get all files that Crowdin pushed
    paths = []
    if config:
        files = ['%s/config/%s' % (_DIR, config)]
    else:
        files = ['%s/config/%s.yaml' % (_DIR, branch),
                 '%s/config/%s_aosp.yaml' % (_DIR, branch)]
    for c in files:
        cmd = ['crowdin', '--config=%s' % c, 'list', 'project',
               '--branch=%s' % branch]
        comm, ret = run_subprocess(cmd)
        if ret != 0:
            sys.exit(ret)
        for p in str(comm[0]).split("\n"):
            paths.append(p.replace('/%s' % branch, ''))

    print('\nUploading translations to Gerrit')
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

        # Usually the project root is everything before /res
        # but there are special cases where /res is part of the repo name as well
        parts = path.split("/res")
        if len(parts) == 2:
            result = parts[0]
        elif len(parts) == 3:
            result = parts[0] + '/res' + parts[1]
        else:
            print('WARNING: Splitting the path not successful for [%s], skipping' % path)
            continue

        result = result.strip('/')
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

        # Search android/default.xml or config/%(branch)_extra_packages.xml
        # for the project's name
        resultPath = None
        resultProject = None
        for project in items:
            path = project.attributes['path'].value
            if not (result + '/').startswith(path +'/'):
                continue
            # We want the longest match, so projects in subfolders of other projects are also
            # taken into account
            if resultPath is None or len(path) > len(resultPath):
                resultPath = path
                resultProject = project

        # Just in case no project was found
        if resultPath is None:
            continue

        if result != resultPath:
            if resultPath in all_projects:
                continue
            result = resultPath
            all_projects.append(result)

        br = resultProject.getAttribute('revision') or branch

        push_as_commit(files, base_path, result,
                       resultProject.getAttribute('name'), br, username)


def main():
    args = parse_args()
    default_branch = args.branch

    if args.submit:
        if args.username is None:
            print('Argument -u/--username is required for submitting!')
            sys.exit(1)
        submit_gerrit(default_branch, args.username)
        sys.exit(0)

    base_path_branch_suffix = default_branch.replace('-', '_').replace('.', '_').upper()
    base_path_env = 'LINEAGE_CROWDIN_BASE_PATH_%s' % base_path_branch_suffix
    base_path = os.getenv(base_path_env)
    if base_path is None:
        cwd = os.getcwd()
        print('You have not set %s. Defaulting to %s' % (base_path_env, cwd))
        base_path = cwd
    if not os.path.isdir(base_path):
        print('%s is not a real directory: %s' % (base_path_env, base_path))
        sys.exit(1)

    if not check_dependencies():
        sys.exit(1)

    xml_android = load_xml(x='%s/android/default.xml' % base_path)
    if xml_android is None:
        sys.exit(1)

    xml_extra = load_xml(x='%s/config/%s_extra_packages.xml'
                           % (_DIR, default_branch))
    if xml_extra is None:
        sys.exit(1)

    xml_snippet = load_xml(x='%s/android/snippets/lineage.xml' % base_path)
    if xml_snippet is None:
        xml_snippet = load_xml(x='%s/android/snippets/cm.xml' % base_path)
    if xml_snippet is None:
        xml_snippet = load_xml(x='%s/android/snippets/hal_cm_all.xml' % base_path)
    if xml_snippet is not None:
        xml_files = (xml_android, xml_snippet, xml_extra)
    else:
        xml_files = (xml_android, xml_extra)

    if args.config:
        files = ['%s/config/%s' % (_DIR, args.config)]
    else:
        files = ['%s/config/%s.yaml' % (_DIR, default_branch),
                 '%s/config/%s_aosp.yaml' % (_DIR, default_branch)]
    if not check_files(files):
        sys.exit(1)

    if args.download and args.username is None:
        print('Argument -u/--username is required for translations download')
        sys.exit(1)

    if args.upload_sources:
        upload_sources_crowdin(default_branch, args.config)
    if args.upload_translations:
        upload_translations_crowdin(default_branch, args.config)
    if args.download:
        download_crowdin(base_path, default_branch, xml_files,
                         args.username, args.config)

    if _COMMITS_CREATED:
        print('\nDone!')
        sys.exit(0)
    else:
        print('\nNothing to commit')
        sys.exit(-1)

if __name__ == '__main__':
    main()
