#!/usr/bin/python2
# -*- coding: utf-8 -*-
# cm_crowdin_sync_all.py
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

def get_caf_additions(strings_base, strings_cm):
    # Load AOSP file and resources
    xml_base = minidom.parse(strings_base)
    list_base_string = xml_base.getElementsByTagName('string')
    list_base_string_array = xml_base.getElementsByTagName('string-array')
    list_base_plurals = xml_base.getElementsByTagName('plurals')
    # Load CM file and resources
    xml_cm = minidom.parse(strings_cm)
    list_cm_string = xml_cm.getElementsByTagName('string')
    list_cm_string_array = xml_cm.getElementsByTagName('string-array')
    list_cm_plurals = xml_cm.getElementsByTagName('plurals')

    # Load all names from AOSP
    names_base_string = []
    names_base_string_array = []
    names_base_plurals = []

    for s in list_base_string :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate'):
            names_base_string.append(s.attributes['name'].value)
    for s in list_base_string_array :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate'):
            names_base_string_array.append(s.attributes['name'].value)
    for s in list_base_plurals :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate'):
            names_base_plurals.append(s.attributes['name'].value)

    # Store all differences in this list
    caf_additions = []

    # Loop through all CM resources. If an ID cannot be found in AOSP base file,
    # the ID is from CAF and will be added to 'caf_additions'
    for s in list_cm_string :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate') and not s.attributes['name'].value in names_base_string:
            caf_additions.append('    ' + s.toxml())
    for s in list_cm_string_array :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate') and not s.attributes['name'].value in names_base_string_array:
            caf_additions.append('    ' + s.toxml())
    for s in list_cm_plurals :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate') and not s.attributes['name'].value in names_base_plurals:
            caf_additions.append('    ' + s.toxml())

    # Done
    return caf_additions

def purge_caf_additions(strings_base, strings_cm):
    # Load AOSP file and resources
    xml_base = minidom.parse(strings_base)
    list_base_string = xml_base.getElementsByTagName('string')
    list_base_string_array = xml_base.getElementsByTagName('string-array')
    list_base_plurals = xml_base.getElementsByTagName('plurals')
    # Load CM file and resources
    xml_cm = minidom.parse(strings_cm)
    list_cm_string = xml_cm.getElementsByTagName('string')
    list_cm_string_array = xml_cm.getElementsByTagName('string-array')
    list_cm_plurals = xml_cm.getElementsByTagName('plurals')
    with codecs.open(strings_cm, 'r', 'utf-8') as f:
        content = [line.rstrip() for line in f]
    shutil.copyfile(strings_cm, strings_cm + '.backup')
    file_this = codecs.open(strings_cm, 'w', 'utf-8')

    # All names from AOSP
    names_base_string = []
    names_base_string_array = []
    names_base_plurals = []

    # Get all names from AOSP
    for s in list_base_string :
        names_base_string.append(s.attributes['name'].value)
    for s in list_base_string_array :
        names_base_string_array.append(s.attributes['name'].value)
    for s in list_base_plurals :
        names_base_plurals.append(s.attributes['name'].value)

    # Get all names from CM
    content2 = []
    for s in list_cm_string :
        name = s.attributes['name'].value
        if name not in names_base_string:
            true = 0
            content2 = []
            for i in content:
                if true == 0:
                    test = re.search('(<string name=\"' + name + ')', i)
                    if test is not None:
                        test2 = re.search('(</string>)', i)
                        if test2:
                            true = 2
                        else:
                            true = 1
                        i = ''
                elif true == 1:
                    test2 = re.search('(</string>)', i)
                    if test2 is not None:
                        true = 2
                    i = ''
                elif true == 2:
                    true = 3
                content2.append(i)
            content = content2
    for s in list_cm_string_array :
        name = s.attributes['name'].value
        if name not in names_base_string_array:
            true = 0
            content2 = []
            for i in content:
                if true == 0:
                    test = re.search('(<string-array name=\"' + name + ')', i)
                    if test is not None:
                        test2 = re.search('(</string-array>)', i)
                        if test2:
                            true = 2
                        else:
                            true = 1
                        i = ''
                elif true == 1:
                    test2 = re.search('(</string-array>)', i)
                    if test2 is not None:
                        true = 2
                    i = ''
                elif true == 2:
                    true = 3
                content2.append(i)
            content = content2
    for s in list_cm_plurals :
        name = s.attributes['name'].value
        if name not in names_base_plurals:
            true = 0
            content2 = []
            for i in content:
                if true == 0:
                    test = re.search('(<plurals name=\"' + name + ')', i)
                    if test is not None:
                        test2 = re.search('(</plurals>)', i)
                        if test2:
                            true = 2
                        else:
                            true = 1
                        i = ''
                elif true == 1:
                    test2 = re.search('(</plurals>)', i)
                    if test2 is not None:
                        true = 2
                    i = ''
                elif true == 2:
                    # The actual purging is done!
                    true = 3
                content2.append(i)
            content = content2

    for addition in content:
        file_this.write(addition + '\n')
    file_this.close()

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
    repo.git.push('ssh://' + username + '@review.cyanogenmod.org:29418/' + name, 'HEAD:refs/for/' + branch)

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
        doc = xml.dom.minidom.Document()
        header = doc.createElement('resources')
        file_write = codecs.open(path + 'en.xml', 'w', 'utf-8')
    else:
        # Open translation files
        file_write = codecs.open(path + lang + '.js', 'w', 'utf-8')
        xml_base = xml.dom.minidom.parse(path + lang + '.xml')
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

print('Welcome to the CM Crowdin sync script!')

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

# Check for crowdin/caf.xml
if not os.path.isfile('crowdin/caf.xml'):
    sys.exit('You have no crowdin/caf.xml. Terminating.')
else:
    print('Found: crowdin/caf.xml')

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

print('\nSTEP 0B: Define shared variables')

# Variables regarding crowdin/caf.xml
print('Loading: crowdin/caf.xml')
xml = minidom.parse('crowdin/caf.xml')
items = xml.getElementsByTagName('item')

# Gerrit user name
username = 'your_nickname'
print('Gerrit username: ' + username)

# Default branch
default_branch = 'cm-11.0'
print('Default branch: ' + default_branch)

print('\nSTEP 0C: Download AOSP base files')
for item in items:
    path_to_values = item.attributes["path"].value
    subprocess.call(['mkdir', '-p', 'tmp/' + path_to_values])
    for aosp_item in item.getElementsByTagName('aosp'):
        url = aosp_item.firstChild.nodeValue
        xml_file = aosp_item.attributes["file"].value
        path_to_base = 'tmp/' + path_to_values + '/' + xml_file
        urlretrieve(url, path_to_base)
        print('Downloaded: ' + path_to_base)

print('\nSTEP 1: Remove CAF additions (non-AOSP supported languages)')
# Store all created cm_caf.xml files in here.
# Easier to remove them afterwards, as they cannot be committed
cm_caf_add = []

for item in items:
    # Create tmp dir for download of AOSP base file
    path_to_values = item.attributes["path"].value
    for aosp_item in item.getElementsByTagName('aosp'):
        xml_file = aosp_item.attributes["file"].value
        path_to_base = 'tmp/' + path_to_values + '/' + xml_file
        path_to_cm = path_to_values + '/' + xml_file
        purge_caf_additions(path_to_base, path_to_cm)
        cm_caf_add.append(path_to_cm)
        print('Purged ' + path_to_cm + ' from CAF additions')

print('\nSTEP 2: Upload Crowdin source translations (non-AOSP supported languages')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_aosp.yaml', 'upload', 'sources']))

print('\nSTEP 3: Revert removal of CAF additions (non-AOSP supported languages)')
for purged_file in cm_caf_add:
    os.remove(purged_file)
    shutil.move(purged_file + '.backup', purged_file)
    print('Reverted purged file ' + purged_file)

print('\nSTEP 4: Create source cm_caf.xmls (AOSP supported languages)')
# Store all created cm_caf.xml files in here.
# Easier to remove them afterwards, as they cannot be committed
cm_caf = []

for item in items:
    # Create tmp dir for download of AOSP base file
    path_to_values = item.attributes["path"].value
    # Create cm_caf.xml - header
    f = codecs.open(path_to_values + '/cm_caf.xml', 'w', 'utf-8')
    f.write('<?xml version="1.0" encoding="utf-8"?>\n')
    f.write('<!--\n')
    f.write('     Copyright (C) 2014 The CyanogenMod Project\n')
    f.write('\n')
    f.write('     Licensed under the Apache License, Version 2.0 (the "License");\n')
    f.write('     you may not use this file except in compliance with the License.\n')
    f.write('     You may obtain a copy of the License at\n')
    f.write('\n')
    f.write('          http://www.apache.org/licenses/LICENSE-2.0\n')
    f.write('\n')
    f.write('     Unless required by applicable law or agreed to in writing, software\n')
    f.write('     distributed under the License is distributed on an "AS IS" BASIS,\n')
    f.write('     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n')
    f.write('     See the License for the specific language governing permissions and\n')
    f.write('     limitations under the License.\n')
    f.write('-->\n')
    f.write('<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n')
    # Create cm_caf.xml - contents
    # This means we also support multiple base files (e.g. checking if strings.xml and arrays.xml are changed)
    contents = []
    item_aosp = item.getElementsByTagName('aosp')
    for aosp_item in item_aosp:
        xml_file = aosp_item.attributes["file"].value
        path_to_base = 'tmp/' + path_to_values + '/' + xml_file
        path_to_cm = path_to_values + '/' + xml_file
        contents = contents + get_caf_additions(path_to_base, path_to_cm)
    for addition in contents:
        f.write(addition + '\n')
    # Create cm_caf.xml - the end
    f.write('</resources>')
    f.close()
    cm_caf.append(path_to_values + '/cm_caf.xml')
    print('Created ' + path_to_values + '/cm_caf.xml')

print('\nSTEP 5: Upload Crowdin source translations (AOSP supported languages)')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_cm.yaml', 'upload', 'sources']))

print('\nSTEP 6A: Download Crowdin translations (AOSP supported languages)')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_cm.yaml', 'download']))

print('\nSTEP 6B: Download Crowdin translations (non-AOSP supported languages)')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_aosp.yaml', 'download']))

print('\nSTEP 7: Remove temp dir')
# We are done with cm_caf.xml files, so remove tmp/
shutil.rmtree(os.getcwd() + '/tmp')

print('\nSTEP 8: Remove useless empty translations')
# Some line of code that I found to find all XML files
result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd()) for f in filenames if os.path.splitext(f)[1] == '.xml']
empty_contents = {'<resources/>', '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>', '<resources xmlns:android="http://schemas.android.com/apk/res/android" xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>'}
for xml_file in result:
    for line in empty_contents:
        if line in open(xml_file).read():
            print('Removing ' + xml_file)
            os.remove(xml_file)

print('\nSTEP 9: Create a list of pushable translations')
# Get all files that Crowdin pushed
proc = subprocess.Popen(['crowdin-cli -c crowdin/crowdin_cm.yaml list sources && crowdin-cli -c crowdin/crowdin_aosp.yaml list sources'], stdout=subprocess.PIPE, shell=True)
proc.wait() # Wait for the above to finish

print('\nSTEP 10: Remove unwanted source cm_caf.xmls (AOSP supported languages)')
# Remove all cm_caf.xml files, which you can find in the list 'cm_caf'
for cm_caf_file in cm_caf:
    print('Removing ' + cm_caf_file)
    os.remove(cm_caf_file)

print('\nSTEP 11: Commit to Gerrit')
xml = minidom.parse('android/default.xml')
xml_extra = minidom.parse('crowdin/extra_packages.xml')
items = xml.getElementsByTagName('project')
items += xml_extra.getElementsByTagName('project')
all_projects = []

for path in iter(proc.stdout.readline,''):
    # Remove the \n at the end of each line
    path = path.rstrip()

    # Get project root dir from Crowdin's output by regex
    m = re.search('/(.*Superuser)/Superuser.*|/(.*LatinIME).*|/(frameworks/base).*|/(.*CMFileManager).*|/(device/.*/.*)/.*/res/values.*|/(hardware/.*/.*)/.*/res/values.*|/(.*)/res/values.*', path)
    results = m.groups()

    if not results:
        # Regex result is empty, warn the user
        print('WARNING: Cannot determine project root dir of [' + path + '], skipping')
        continue

    # Determine the true match of the regex
    [tuple(filter(None, i)) for i in results] # remove None from regex tuple
    result = results[0] # select the only left-over result

    if good_path in all_projects:
        # Already committed for this project, go to next project
        continue

    # When a project has multiple translatable files, Crowdin will give duplicates.
    # We don't want that (useless empty commits), so we save each project in all_projects
    # and check if it's already in there.
    all_projects.append(good_path)

    # Search in android/default.xml or crowdin/extra_packages.xml for the project's name
    for project_item in items:
        if project_item.attributes['path'].value != good_path:
            # No match found, go to next item
            continue

        # Define branch (custom branch if defined in xml file, otherwise 'cm-11.0'
        if project_item.hasAttribute('revision'):
            branch = project_item.attributes['revision'].value
        else:
            branch = default_branch

        push_as_commit(good_path, project_item.attributes['name'].value, branch, username)

print('\nDone!')
