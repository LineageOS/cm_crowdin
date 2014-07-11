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

# Check for crowdin/crowdin_aosp.xml
if not os.path.isfile('crowdin/crowdin_aosp.xml'):
    sys.exit('You have no crowdin/crowdin_aosp.xml. Terminating.')
else:
    print('Found: crowdin/crowdin_cm.xml')

# Check for crowdin/crowdin_cm.xml
if not os.path.isfile('crowdin/crowdin_cm.xml'):
    sys.exit('You have no crowdin/crowdin_cm.xml. Terminating.')
else:
    print('Found: crowdin/crowdin_cm.xml')

# Check for caf.xml
if not os.path.isfile('caf.xml'):
    sys.exit('You have no caf.xml. Terminating.')
else:
    print('Found: caf.xml')

# Check for extra_packages.xml
if not os.path.isfile('extra_packages.xml'):
    sys.exit('You have no extra_packages.xml. Terminating.')
else:
    print('Found: extra_packages.xml')

print('\nSTEP 1: Remove CAF additions (non-AOSP supported languages)')
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

print('\nSTEP 2: Upload Crowdin source translations (non-AOSP supported languages')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_aosp.yaml', 'upload', 'sources']))

print('\nSTEP 4A: Revert removal of CAF additions (non-AOSP supported languages)')
for purged_file in cm_caf_add:
    os.remove(purged_file)
    shutil.move(purged_file + '.backup', purged_file)
    print('Reverted purged file ' + purged_file)

print('\nSTEP 4: Create source cm_caf.xmls (AOSP supported languages)')
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

print('\nSTEP 5: Upload Crowdin source translations (AOSP supported languages')
# Execute 'crowdin-cli upload sources' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_aosp.yaml', 'upload', 'sources']))

print('\nSTEP 6A: Download Crowdin translations (AOSP supported languages')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_aosp.yaml', 'download']))

print('\nSTEP 6B: Download Crowdin translations (non-AOSP supported languages')
# Execute 'crowdin-cli download' and show output
print(subprocess.check_output(['crowdin-cli', '-c', 'crowdin/crowdin_cm.yaml', 'download']))

print('\nSTEP 7: Remove temp dir')
# We are done with cm_caf.xml files, so remove tmp/
shutil.rmtree(os.getcwd() + '/tmp')

print('\nSTEP 8: Remove useless empty translations')
# Some line of code that I found to find all XML files
result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd()) for f in filenames if os.path.splitext(f)[1] == '.xml']
for xml_file in result:
    # We hate empty, useless files. Crowdin exports them with <resources/> (sometimes with xliff).
    # That means: easy to find
    if '<resources/>' in open(xml_file).read():
        print('Removing ' + xml_file)
        os.remove(xml_file)
    elif '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>' in open(xml_file).read():
        print('Removing ' + xml_file)
        os.remove(xml_file)
    elif '<resources xmlns:android="http://schemas.android.com/apk/res/android" xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>' in open(xml_file).read():
        print('Removing ' + xml_file)
        os.remove(xml_file)

print('\nSTEP 9: Create a list of pushable translations')
# Get all files that Crowdin pushed
proc = subprocess.Popen(['crowdin-cli', 'list', 'sources'],stdout=subprocess.PIPE)
print(subprocess.check_output(['crowdin-cli', 'list', 'sources'])) # seems to fix some problems when the above is executed

print('\nSTEP 10: Remove unwanted source cm_caf.xmls (AOSP supported languages)')
# Remove all cm_caf.xml files, which you can find in the list 'cm_caf'
for cm_caf_file in cm_caf:
    print('Removing ' + cm_caf_file)
    os.remove(cm_caf_file)

print('\nSTEP 7: Commit to Gerrit')
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
                if project_item.attributes['path'].value == good_path:
                    if project_item.hasAttribute('revision'):
                        branch = project_item.attributes['revision'].value
                    else:
                        branch = 'cm-11.0'
                    print('Committing ' + project_item.attributes['name'].value + ' on branch ' + branch + ' (based on android/default.xml or extra_packages.xml)')
                    push_as_commit(good_path, project_item.attributes['name'].value, branch)

print('\nDone!')
