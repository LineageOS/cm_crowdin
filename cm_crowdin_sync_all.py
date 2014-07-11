#!/usr/bin/python2
# -*- coding: utf-8 -*-
# cm_crowdin_sync.py
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

    # All names from CM
    names_cm_string = []
    names_cm_string_array = []
    names_cm_plurals = []
    # All names from AOSP
    names_base_string = []
    names_base_string_array = []
    names_base_plurals = []

    # Get all names from CM
    for s in list_cm_string :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate'):
            names_cm_string.append(s.attributes['name'].value)
    for s in list_cm_string_array :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate'):
            names_cm_string_array.append(s.attributes['name'].value)
    for s in list_cm_plurals :
        if not s.hasAttribute('translatable') and not s.hasAttribute('translate'):
            names_cm_plurals.append(s.attributes['name'].value)
    # Get all names from AOSP
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

    # Store all found strings/arrays/plurals.
    # Prevent duplicates with product attribute
    found_string = []
    found_string_array = []
    found_plurals = []

    # Add all CAF additions to the list 'caf_additions'
    for z in names_cm_string:
        if z not in names_base_string and z not in found_string:
            for string_item in list_cm_string:
                if string_item.attributes['name'].value == z:
                    caf_additions.append('    ' + string_item.toxml())
            found_string.append(z)
    for y in names_cm_string_array:
        if y not in names_base_string_array and y not in found_string_array:
            for string_array_item in list_cm_string_array:
                if string_array_item.attributes['name'].value == y:
                    caf_additions.append('    ' + string_array_item.toxml())
            found_string_array.append(y)
    for x in names_cm_plurals:
        if x not in names_base_plurals and x not in found_plurals:
            for plurals_item in list_cm_plurals:
                if plurals_item.attributes['name'].value == x:
                    caf_additions.append('    ' + plurals_item.toxml())
            found_plurals.append(x)

    # Done :-)
    return caf_additions

def push_as_commit(path, name, branch):
    # CM gerrit nickname
    username = 'your_nickname'

    # Get path
    path = os.getcwd() + '/' + path

    # Create git commit
    repo = git.Repo(path)
    removed_files = repo.git.ls_files(d=True).split('\n')
    try:
        repo.git.rm(removed_files)
    except:
        pass
    repo.git.add('-A')
    try:
        repo.git.commit(m='Automatic translation import')
    except:
        print('Failed to create commit for ' + name + ', probably empty: skipping')
        return
    repo.git.push('ssh://' + username + '@review.cyanogenmod.org:29418/' + name, 'HEAD:refs/for/' + branch)
    print('Succesfully pushed commit for ' + name)

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

print('\nSTEP 1: Create source cm_caf.xml (for AOSP-supported languages)')
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
        url = aosp_item.firstChild.nodeValue
        xml_file = aosp_item.attributes["file"].value
        path_to_base = 'tmp/' + path_to_values + '/' + xml_file
        path_to_cm = path_to_values + '/' + xml_file
        urlretrieve(url, path_to_base)
        contents = contents + get_caf_additions(path_to_base, path_to_cm)
    for addition in contents:
        f.write(addition + '\n')
    # Create cm_caf.xml - the end
    f.write('</resources>')
    f.close()
    cm_caf.append(path_to_values + '/cm_caf.xml')
    print('Created ' + path_to_values + '/cm_caf.xml')

print('\nSTEP 2: Remove CAF additions (for non-AOSP-supported languages)')
# Load caf.xml
print('Loading caf.xml')
xml = minidom.parse('caf.xml')
items = xml.getElementsByTagName('item')

# Store all created cm_caf.xml files in here.
# Easier to remove them afterwards, as they cannot be committed
cm_caf_add = []

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
        cm_caf_add.append(path_to_cm)
        print('Purged ' + path_to_cm + ' from CAF additions')
