#!/usr/bin/python2
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

############################################# IMPORTS ##############################################

import argparse
import codecs
import git
import os
import os.path
import re
import shutil
import subprocess
import sys
from urllib import urlretrieve
from xml.dom import minidom

############################################ FUNCTIONS #############################################

def push_as_commit(path, name, branch, username):
    print('Committing ' + name + ' on branch ' + branch)

    # Get path
    path = os.getcwd() + '/' + path

    # Create repo object
    repo = git.Repo(path)

    # Remove previously deleted files from Git
    removed_files = repo.git.ls_files(d=True).split('\n')
    try:
        repo.git.rm(removed_files)
    except:
        pass

    # Add all files to commit
    repo.git.add('-A')

    # Create commit; if it fails, probably empty so skipping
    try:
        repo.git.commit(m='Automatic translation import')
    except:
        print('Failed to create commit for ' + name + ', probably empty: skipping')
        return

    # Push commit
    try:
        repo.git.push('ssh://' + username + '@review.cyanogenmod.org:29418/' + name, 'HEAD:refs/for/' + branch + '%topic=translation')
        print('Succesfully pushed commit for ' + name)
    except:
        print('Failed to push commit for ' + name)

def run_command(cmd):
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    ret = p.wait()
    if ret != 0:
        print("Failed to run cmd: %s" % " ".join(cmd))
        sys.exit(ret)

####################################################################################################

parser = argparse.ArgumentParser(description='Synchronising CyanogenMod\'s translations with Crowdin')
sync = parser.add_mutually_exclusive_group()
parser.add_argument('-u', '--username', help='Gerrit username', required=True)
parser.add_argument('-b', '--branch', help='CyanogenMod branch', required=True)
sync.add_argument('--no-upload', action='store_true', help='Only download CM translations from Crowdin')
sync.add_argument('--no-download', action='store_true', help='Only upload CM source translations to Crowdin')
args = parser.parse_args()
argsdict = vars(args)

username = argsdict['username']
default_branch = argsdict['branch']

####################################################################################################

print('Welcome to the CM Crowdin sync script!')

############################################# PREPARE ##############################################

print('\nSTEP 0: Checking dependencies & define shared variables')
# Check for Ruby version of crowdin-cli
if subprocess.check_output(['rvm', 'all', 'do', 'gem', 'list', 'crowdin-cli', '-i']) == 'true':
    sys.exit('You have not installed crowdin-cli. Terminating.')
else:
    print('Found: crowdin-cli')

# Check for repo
try:
    subprocess.check_output(['which', 'repo'])
except:
    sys.exit('You have not installed repo. Terminating.')

# Check for android/default.xml
if not os.path.isfile('android/default.xml'):
    sys.exit('You have no android/default.xml. Terminating.')
else:
    print('Found: android/default.xml')

# Variables regarding android/default.xml
print('Loading: android/default.xml')
xml_android = minidom.parse('android/default.xml')

# Check for crowdin/extra_packages_' + default_branch + '.xml
if not os.path.isfile('crowdin/extra_packages_' + default_branch + '.xml'):
    sys.exit('You have no crowdin/extra_packages_' + default_branch + '.xml. Terminating.')
else:
    print('Found: crowdin/extra_packages_' + default_branch + '.xml')

# Check for crowdin/config.yaml
if not os.path.isfile('crowdin/config.yaml'):
    sys.exit('You have no crowdin/config.yaml. Terminating.')
else:
    print('Found: crowdin/config.yaml')

# Check for crowdin/config_aosp.yaml
if not os.path.isfile('crowdin/config_aosp.yaml'):
    sys.exit('You have no crowdin/config_aosp.yaml. Terminating.')
else:
    print('Found: crowdin/config_aosp.yaml')

# Check for crowdin/crowdin_' + default_branch + '.yaml
if not os.path.isfile('crowdin/crowdin_' + default_branch + '.yaml'):
    sys.exit('You have no crowdin/crowdin_' + default_branch + '.yaml. Terminating.')
else:
    print('Found: crowdin/crowdin_' + default_branch + '.yaml')

# Check for crowdin/crowdin_' + default_branch + '_aosp.yaml
if not os.path.isfile('crowdin/crowdin_' + default_branch + '_aosp.yaml'):
    sys.exit('You have no crowdin/crowdin_' + default_branch + '_aosp.yaml. Terminating.')
else:
    print('Found: crowdin/crowdin_' + default_branch + '_aosp.yaml')

############################################### MAIN ###############################################

if not args.no_upload:
    print('\nSTEP 1: Upload Crowdin source translations')
    print('Uploading Crowdin source translations (AOSP supported languages)')
    # Execute 'crowdin-cli upload sources' and show output
    run_command(['crowdin-cli', '--config=crowdin/crowdin_' + default_branch + '.yaml', '--identity=crowdin/config.yaml', 'upload', 'sources'])

    print('Uploading Crowdin source translations (non-AOSP supported languages)')
    # Execute 'crowdin-cli upload sources' and show output
    run_command(['crowdin-cli', '--config=crowdin/crowdin_' + default_branch + '_aosp.yaml', '--identity=crowdin/config_aosp.yaml', 'upload', 'sources'])
else:
    print('\nSkipping source translations upload')

if not args.no_download:
    print('\nSTEP 2: Download Crowdin translations')
    print('Downloading Crowdin translations (AOSP supported languages)')
    # Execute 'crowdin-cli download' and show output
    run_command(['crowdin-cli', '--config=crowdin/crowdin_' + default_branch + '.yaml', '--identity=crowdin/config.yaml', 'download'])

    print('Downloading Crowdin translations (non-AOSP supported languages)')
    # Execute 'crowdin-cli download' and show output
    run_command(['crowdin-cli', '--config=crowdin/crowdin_' + default_branch + '_aosp.yaml', '--identity=crowdin/config_aosp.yaml', 'download'])

    print('\nSTEP 3: Remove useless empty translations')
    # Some line of code that I found to find all XML files
    result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd()) for f in filenames if os.path.splitext(f)[1] == '.xml']
    empty_contents = {'<resources/>', '<resources xmlns:android="http://schemas.android.com/apk/res/android"/>', '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>', '<resources xmlns:android="http://schemas.android.com/apk/res/android" xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>'}
    for xml_file in result:
        for line in empty_contents:
            if line in open(xml_file).read():
                print('Removing ' + xml_file)
                os.remove(xml_file)
                break

    print('\nSTEP 4: Create a list of pushable translations')
    # Get all files that Crowdin pushed
    proc = subprocess.Popen(['crowdin-cli --config=crowdin/crowdin_' + default_branch + '.yaml --identity=crowdin/config.yaml list sources | grep "' + default_branch + '" | sed "s#/' + default_branch + '##g" && crowdin-cli --config=crowdin/crowdin_' + default_branch + '_aosp.yaml --identity=crowdin/config_aosp.yaml list sources | grep "' + default_branch + '" | sed "s#/' + default_branch + '##g"'], stdout=subprocess.PIPE, shell=True)
    proc.wait() # Wait for the above to finish

    print('\nSTEP 5: Upload to Gerrit')
    xml_extra = minidom.parse('crowdin/extra_packages_' + default_branch + '.xml')
    items = xml_android.getElementsByTagName('project')
    items += xml_extra.getElementsByTagName('project')
    all_projects = []

    for path in iter(proc.stdout.readline,''):
        # Remove the \n at the end of each line
        path = path.rstrip()

        if not path:
            continue

        # Get project root dir from Crowdin's output by regex
        m = re.search('/(.*LatinIME).*|/(frameworks/base).*|/(.*CMFileManager).*|/(device/.*/.*)/.*/res/values.*|/(hardware/.*/.*)/.*/res/values.*|/(.*)/res/values.*', path)

        if not m.groups():
            # Regex result is empty, warn the user
            print('WARNING: Cannot determine project root dir of [' + path + '], skipping')
            continue

        for i in m.groups():
            if not i:
                continue
            result = i
            break

        if result in all_projects:
            # Already committed for this project, go to next project
            continue

        # When a project has multiple translatable files, Crowdin will give duplicates.
        # We don't want that (useless empty commits), so we save each project in all_projects
        # and check if it's already in there.
        all_projects.append(result)

        # Search in android/default.xml or crowdin/extra_packages_' + default_branch + '.xml for the project's name
        for project_item in items:
            if project_item.attributes['path'].value != result:
                # No match found, go to next item
                continue

            # Define branch (custom branch if defined in xml file, otherwise the default one)
            if project_item.hasAttribute('revision'):
                branch = project_item.attributes['revision'].value
            else:
                branch = default_branch

            push_as_commit(result, project_item.attributes['name'].value, branch, username)
else:
    print('\nSkipping translations download')

############################################### DONE ###############################################

print('\nDone!')
