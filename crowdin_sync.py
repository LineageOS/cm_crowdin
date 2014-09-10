#!/usr/bin/python2
# -*- coding: utf-8 -*-
# crowdin_sync.py
#
# Updates Crowdin source translations and pushes translations
# directly to CyanogenMod's Gerrit.
#
# Copyright (C) 2014 The CyanogenMod Project
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

def get_default_branch(xml):
    xml_default = xml.getElementsByTagName('default')[0]
    xml_default_revision = xml_default.attributes['revision'].value
    return re.search('refs/heads/(.*)', xml_default_revision).groups()[0]

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
    repo.git.push('ssh://' + username + '@review.cyanogenmod.org:29418/' + name, 'HEAD:refs/for/' + branch + '%topic=translation')

    print('Succesfully pushed commit for ' + name)

def sync_js_translations(sync_type, path, lang=''):
    # lang is necessary in download mode
    if sync_type == 'download' and lang == '':
        sys.exit('Invalid syntax. Language code is required in download mode.')

    # Read source en.js file. This is necessary for both upload and download modes
    with codecs.open(path + 'en.js', 'r', 'utf-8') as f:
        content = f.readlines()

    if sync_type == 'upload':
        # Prepare XML file structure
        doc = minidom.Document()
        header = doc.createElement('resources')
        file_write = codecs.open(path + 'en.xml', 'w', 'utf-8')
    else:
        # Open translation files
        file_write = codecs.open(path + lang + '.js', 'w', 'utf-8')
        xml_base = minidom.parse(path + lang + '.xml')
        tags = xml_base.getElementsByTagName('string')

    # Read each line of en.js
    for a_line in content:
        # Regex to determine string id
        m = re.search(' (.*): [\'|\"]', a_line)
        if m is not None:
            for string_id in m.groups():
                if string_id is not None:
                    # Find string id
                    string_id = string_id.replace(' ', '')
                    m2 = re.search('\'(.*)\'|"(.*)"', a_line)
                    # Find string contents
                    for string_content in m2.groups():
                        if string_content is not None:
                            break
                    if sync_type == 'upload':
                        # In upload mode, create the appropriate string element.
                        contents = doc.createElement('string')
                        contents.attributes['name'] = string_id
                        contents.appendChild(doc.createTextNode(string_content))
                        header.appendChild(contents)
                    else:
                        # In download mode, check if string_id matches a name attribute in the translation XML file.
                        # If it does, replace English text with the translation.
                        # If it does not, English text will remain and will be added to the file to retain the file structure.
                        for string in tags:
                            if string.attributes['name'].value == string_id:
                                a_line = a_line.replace(string_content.rstrip(), string.firstChild.nodeValue)
                                break
                    break
        # In download mode do not write comments
        if sync_type == 'download' and not '//' in a_line:
            # Add language identifier (1)
            if 'cmaccount.l10n.en' in a_line:
                a_line = a_line.replace('l10n.en', 'l10n.' + lang)
            # Add language identifier (2)
            if 'l10n.add(\'en\'' in a_line:
                a_line = a_line.replace('l10n.add(\'en\'', 'l10n.add(\'' + lang + '\'')
            # Now write the line
            file_write.write(a_line)

    # Create XML file structure
    if sync_type == 'upload':
        header.appendChild(contents)
        contents = header.toxml().replace('<string', '\n    <string').replace('</resources>', '\n</resources>')
        file_write.write('<?xml version="1.0" encoding="utf-8"?>\n')
        file_write.write('<!-- .JS CONVERTED TO .XML - DO NOT MERGE THIS FILE -->\n')
        file_write.write(contents)

    # Close file
    file_write.close()

###################################################################################################

print('Welcome to the CM Crowdin sync script!')

###################################################################################################

parser = argparse.ArgumentParser(description='Synchronising CyanogenMod\'s translations with Crowdin')
parser.add_argument('--username', help='Gerrit username', required=True)
#parser.add_argument('--upload-only', help='Only upload CM source translations to Crowdin', required=False)
args = vars(parser.parse_args())

username = args['username']

############################################## STEP 0 ##############################################

print('\nSTEP 0A: Checking dependencies')
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

# Check for crowdin/config_aosp.yaml
if not os.path.isfile('crowdin/config_aosp.yaml'):
    sys.exit('You have no crowdin/config_aosp.yaml. Terminating.')
else:
    print('Found: crowdin/config_aosp.yaml')

# Check for crowdin/config_cm.yaml
if not os.path.isfile('crowdin/config_cm.yaml'):
    sys.exit('You have no crowdin/config_cm.yaml. Terminating.')
else:
    print('Found: crowdin/config_cm.yaml')

# Check for crowdin/crowdin_aosp.yaml
if not os.path.isfile('crowdin/crowdin_aosp.yaml'):
    sys.exit('You have no crowdin/crowdin_aosp.yaml. Terminating.')
else:
    print('Found: crowdin/crowdin_aosp.yaml')

# Check for crowdin/crowdin_cm.yaml
if not os.path.isfile('crowdin/crowdin_cm.yaml'):
    sys.exit('You have no crowdin/crowdin_cm.yaml. Terminating.')
else:
    print('Found: crowdin/crowdin_cm.yaml')

# Check for crowdin/extra_packages.xml
if not os.path.isfile('crowdin/extra_packages.xml'):
    sys.exit('You have no crowdin/extra_packages.xml. Terminating.')
else:
    print('Found: crowdin/extra_packages.xml')

# Check for crowdin/js.xml
if not os.path.isfile('crowdin/js.xml'):
    sys.exit('You have no crowdin/js.xml. Terminating.')
else:
    print('Found: crowdin/js.xml')

print('\nSTEP 0B: Define shared variables')

# Variables regarding android/default.xml
print('Loading: android/default.xml')
xml_android = minidom.parse('android/default.xml')

# Variables regarding crowdin/js.xml
print('Loading: crowdin/js.xml')
xml_js = minidom.parse('crowdin/js.xml')
items_js = xml_js.getElementsByTagName('project')

# Default branch
default_branch = get_default_branch(xml_android)
print('Default branch: ' + default_branch)

############################################## STEP 1 ##############################################

print('\nSTEP 1: Upload Crowdin source translations (non-AOSP supported languages)')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '--config=crowdin/crowdin_aosp.yaml', '--identity=crowdin/config_aosp.yaml', 'upload', 'sources']))

############################################## STEP 2 ##############################################

# JS files cannot be translated easily on Crowdin. That's why they are uploaded as Android XML
# files. At this time, the (English) JS source file is converted to an XML file, so Crowdin knows it
# needs to download for it.
#print('\nSTEP 2: Convert .js source translations to .xml')
#
#js_files = []
#
#for item in items_js:
#    path = item.attributes['path'].value + '/'
#    sync_js_translations('upload', path)
#    print('Converted: ' + path + 'en.js to en.xml')
#    js_files.append(path + 'en.js')

############################################## STEP 3 ##############################################

print('\nSTEP 3: Upload Crowdin source translations (AOSP supported languages)')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '--config=crowdin/crowdin_cm.yaml', '--identity=crowdin/config_cm.yaml', 'upload', 'sources']))

############################################## STEP 4 ##############################################

print('\nSTEP 4A: Download Crowdin translations (AOSP supported languages)')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '--config=crowdin/crowdin_cm.yaml', '--identity=crowdin/config_cm.yaml', 'download']))

print('\nSTEP 4B: Download Crowdin translations (non-AOSP supported languages)')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '--config=crowdin/crowdin_aosp.yaml', '--identity=crowdin/config_aosp.yaml', 'download']))

############################################## STEP 5 ##############################################

print('\nSTEP 5: Remove useless empty translations')
# Some line of code that I found to find all XML files
result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd()) for f in filenames if os.path.splitext(f)[1] == '.xml']
empty_contents = {'<resources/>', '<resources xmlns:android="http://schemas.android.com/apk/res/android"/>', '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>', '<resources xmlns:android="http://schemas.android.com/apk/res/android" xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>'}
for xml_file in result:
    for line in empty_contents:
        if line in open(xml_file).read():
            print('Removing ' + xml_file)
            os.remove(xml_file)
            break

#for js_file in js_files:
#    print('Removing ' + js_file)
#    os.remove(js_file)

############################################## STEP 6 ##############################################

print('\nSTEP 6: Create a list of pushable translations')
# Get all files that Crowdin pushed
proc = subprocess.Popen(['crowdin-cli --config=crowdin/crowdin_cm.yaml --identity=crowdin/config_cm.yaml list sources && crowdin-cli --config=crowdin/crowdin_aosp.yaml --identity=crowdin/config_aosp.yaml list sources'], stdout=subprocess.PIPE, shell=True)
proc.wait() # Wait for the above to finish

############################################## STEP 7 ##############################################

#print('\nSTEP 7: Convert JS-XML translations to their JS format')
#
#for item in items_js:
#    path = item.attributes['path'].value
#    all_xml_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd() + '/' + path) for f in filenames if os.path.splitext(f)[1] == '.xml']
#    for xml_file in all_xml_files:
#        lang_code = os.path.splitext(xml_file)[0]
#        sync_js_translations('download', path, lang_code)
#        os.remove(xml_file)
#    os.remove(path + '/' + item.attributes['source'].value)
#

############################################## STEP 8 ##############################################

print('\nSTEP 8: Commit to Gerrit')
xml_extra = minidom.parse('crowdin/extra_packages.xml')
items = xml_android.getElementsByTagName('project')
items += xml_extra.getElementsByTagName('project')
all_projects = []

for path in iter(proc.stdout.readline,''):
    # Remove the \n at the end of each line
    path = path.rstrip()

    if not path:
        continue

    # Get project root dir from Crowdin's output by regex
    m = re.search('/(.*Superuser)/Superuser.*|/(.*LatinIME).*|/(frameworks/base).*|/(.*CMFileManager).*|/(.*CMHome).*|/(device/.*/.*)/.*/res/values.*|/(hardware/.*/.*)/.*/res/values.*|/(.*)/res/values.*', path)

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

    # Search in android/default.xml or crowdin/extra_packages.xml for the project's name
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

############################################### DONE ###############################################

print('\nDone!')
