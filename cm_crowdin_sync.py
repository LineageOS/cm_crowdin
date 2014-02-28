#!/usr/bin/python2
#
# cm_crowdin_sync.py
#
# Updates Crowdin source translations and pulls translations
# directly to CyanogenMod's Git

import create_cm_caf_xml
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

print('Welcome to the CM Crowdin sync script!\n')

print('STEP 0: Checking dependencies\n')
if subprocess.check_output(['rvm', 'all', 'do', 'gem', 'list', 'crowdin-cli', '-i']) == 'true':
    sys.exit('You have not installed crowdin-cli. Terminating.')
if not os.path.isfile('caf.xml'):
    sys.exit('You have no caf.xml. Terminating.')
if not os.path.isfile('default.xml'):
    sys.exit('You have no default.xml. Terminating.')

print('STEP 1: Create cm_caf.xml')
xml = minidom.parse('caf.xml')
items = xml.getElementsByTagName('item')

cm_caf = []

for item in items:
    subprocess.call(['mkdir', '-p', 'tmp/' + item.attributes["path"].value])
    item_aosp = item.getElementsByTagName('aosp')
    for aosp_item in item_aosp:
        url = aosp_item.firstChild.nodeValue
        path_to_base = 'tmp/' + item.attributes["path"].value + '/' + aosp_item.attributes["file"].value
        path_to_cm = item.attributes["path"].value + '/' + aosp_item.attributes["file"].value
        path = item.attributes["path"].value
        urlretrieve(url, path_to_base)
        create_cm_caf_xml.create_cm_caf_xml(path_to_base, path_to_cm, path)
        cm_caf.append(path + '/cm_caf.xml')
        print('Created ' + path + '/cm_caf.xml')

print('\nSTEP 2: Upload Crowdin source translations')
print(subprocess.check_output(['crowdin-cli', 'upload', 'sources']))

print('STEP 3: Download Crowdin translations')
print(subprocess.check_output(['crowdin-cli', "download"]))

print('STEP 4A: Clean up of source cm_caf.xmls')
for cm_caf_file in cm_caf:
    print ('Removing ' + cm_caf_file)
    os.remove(cm_caf_file)

print('\nSTEP 4B: Clean up of temp dir')
shutil.rmtree(os.getcwd() + '/tmp')

print('STEP 4C: Clean up of empty translations')
result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.getcwd()) for f in filenames if os.path.splitext(f)[1] == '.xml']
for xml_file in result:
    if '<resources/>' in open(xml_file).read():
        print ('Removing ' + xml_file)
        os.remove(xml_file)
    elif '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"/>' in open(xml_file).read():
        print ('Removing ' + xml_file)
        os.remove(xml_file)    

print('\nSTEP 5: Push translations to Git')
proc = subprocess.Popen(['crowdin-cli', 'list', 'sources'],stdout=subprocess.PIPE)
xml = minidom.parse('default.xml')
items = xml.getElementsByTagName('project')
all_projects = []

for path in iter(proc.stdout.readline,''):
    path = path.rstrip()
    m = re.search('/(.*Superuser)/Superuser.*|/(.*LatinIME).*|/(frameworks/base).*|/(.*CMFileManager).*|/(device/.*/.*)/.*/res/values.*|/(hardware/.*/.*)/.*/res/values.*|/(.*)/res/values.*', path)
    for good_path in m.groups():
        if good_path is not None and not good_path in all_projects:
            all_projects.append(good_path)
            working = 'false'
            for project_item in items:
                if project_item.attributes["path"].value == good_path:
                    working = 'true'
                    create_cm_caf_xml.push_as_commit(good_path, project_item.attributes['name'].value)
                    print 'WORKING: ' + project_item.attributes['name'].value
            if working == 'false':
                create_cm_caf_xml.push_as_commit(good_path, 'CyanogenMod/android_' + good_path.replace('/', '_'))
                print 'WORKAROUND: ' + good_path

print('STEP 6: Done!')
