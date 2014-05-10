#!/usr/bin/python2
# -*- coding: utf-8 -*-
# cm_crowdin_sync.py
#
# Updates Crowdin source translations and pulls translations
# directly to CyanogenMod's Git.
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
import mmap
import os
import os.path
import re
import shutil
import subprocess
import sys
from urllib import urlretrieve
from xml.dom import minidom

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

def push_as_commit(path, name, branch):
    # CM gerrit nickname
    username = 'your_nickname'

    # Get path
    path = os.getcwd() + '/' + path

    # Create git commit
    repo = git.Repo(path)
    repo.git.add(path)
    try:
        repo.git.commit(m='Automatic translation import')
        repo.git.push('ssh://' + username + '@review.cyanogenmod.org:29418/' + name, 'HEAD:refs/for/' + branch)
        print 'Succesfully pushed commit for ' + name
    except:
        # If git commit fails, it's probably because of no changes.
        # Just continue.
        print 'No commit pushed (probably empty?) for ' + name

print('Welcome to the CM Crowdin sync script!')

print('\nSTEP 0: Checking dependencies')
# Check for Ruby version of crowdin-cli
if subprocess.check_output(['rvm', 'all', 'do', 'gem', 'list', 'crowdin-cli', '-i']) == 'true':
    sys.exit('You have not installed crowdin-cli. Terminating.')
else:
    print('Found: crowdin-cli')
# Check for caf.xml
if not os.path.isfile('caf.xml'):
    sys.exit('You have no caf.xml. Terminating.')
else:
    print('Found: caf.xml')
# Check for android/default.xml
if not os.path.isfile('android/default.xml'):
    sys.exit('You have no android/default.xml. Terminating.')
else:
    print('Found: android/default.xml')
# Check for extra_packages.xml
if not os.path.isfile('extra_packages.xml'):
    sys.exit('You have no extra_packages.xml. Terminating.')
else:
    print('Found: extra_packages.xml')
# Check for repo
try:
    subprocess.check_output(['which', 'repo'])
except:
    sys.exit('You have not installed repo. Terminating.')

print('\nSTEP 1: Removing CAF additions') 
# Load caf.xml
print('Loading caf.xml')
xml = minidom.parse('caf.xml')
items = xml.getElementsByTagName('item')

# Store all created cm_caf.xml files in here.
# Easier to remove them afterwards, as they cannot be committed
cm_caf = []

for item in items:
    # Create tmp dir for download of AOSP base file
    path_to_values = item.attributes["path"].value
    subprocess.call(['mkdir', '-p', 'tmp/' + path_to_values])
    for aosp_item in item.getElementsByTagName('aosp'):
        url = aosp_item.firstChild.nodeValue
        xml_file = aosp_item.attributes["file"].value
        path_to_base = 'tmp/' + path_to_values + '/' + xml_file
        path_to_cm = path_to_values + '/' + xml_file
        urlretrieve(url, path_to_base)
        purge_caf_additions(path_to_base, path_to_cm)
        cm_caf.append(path_to_cm)
        print('Purged ' + path_to_cm + ' from CAF additions')

print('\nSTEP 2: Upload Crowdin source translations')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin-aosp.yaml', 'upload', 'sources']))

print('\nSTEP 3: Download Crowdin translations')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin-aosp.yaml', "download"]))

print('\nSTEP 4A: Revert purges')
for purged_file in cm_caf:
    os.remove(purged_file)
    shutil.move(purged_file + '.backup', purged_file)
    print('Reverted purged file ' + purged_file)

print('\nSTEP 4B: Clean up of temp dir')
# We are done with cm_caf.xml files, so remove tmp/
shutil.rmtree(os.getcwd() + '/tmp')

print('\nSTEP 4C: Clean up of empty translations')
# Some line of code that I found to find all XML files
result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd()) for f in filenames if os.path.splitext(f)[1] == '.xml']
for xml_file in result:
    # We hate empty, useless files. Crowdin exports them with <resources/> (sometimes with xliff).
    # That means: easy to find
    if '<resources/>' in open(xml_file).read():
        print ('Removing ' + xml_file)
        os.remove(xml_file)
    elif '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>' in open(xml_file).read():
        print ('Removing ' + xml_file)
        os.remove(xml_file)    

print('\nSTEP 5: Push translations to Git')
# Get all files that Crowdin pushed
proc = subprocess.Popen(['crowdin-cli', '-c', 'crowdin-aosp.yaml', 'list', 'sources'],stdout=subprocess.PIPE)
xml = minidom.parse('android/default.xml')
xml_extra = minidom.parse('extra_packages.xml')
items = xml.getElementsByTagName('project')
items += xml_extra.getElementsByTagName('project')
all_projects = []

for path in iter(proc.stdout.readline,''):
    # Remove the \n at the end of each line
    path = path.rstrip()
    # Get project root dir from Crowdin's output
    m = re.search('/(.*Superuser)/Superuser.*|/(.*LatinIME).*|/(frameworks/base).*|/(.*CMFileManager).*|/(device/.*/.*)/.*/res/values.*|/(hardware/.*/.*)/.*/res/values.*|/(.*)/res/values.*', path)
    for good_path in m.groups():
        # When a project has multiple translatable files, Crowdin will give duplicates.
        # We don't want that (useless empty commits), so we save each project in all_projects
        # and check if it's already in there.
        if good_path is not None and not good_path in all_projects:
            all_projects.append(good_path)
            for project_item in items:
                # We need to have the Github repository for the git push url.
                # Obtain them from android/default.xml or extra_packages.xml.
                if project_item.attributes["path"].value == good_path:
                    if project_item.hasAttribute('revision'):
                        branch = project_item.attributes['revision'].value
                    else:
                        branch = 'cm-11.0'
                    print 'Committing ' + project_item.attributes['name'].value + ' on branch ' + branch + ' (based on android/default.xml or extra_packages.xml)'
                    push_as_commit(good_path, project_item.attributes['name'].value, branch)

print('\nSTEP 6: Done!')
