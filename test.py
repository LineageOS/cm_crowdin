#!/usr/bin/python2

import os.path
import sys
import cm_sync
from urllib import urlretrieve
from subprocess import call
from xml.dom import minidom

print('STEP 0: Welcome to the CM Crowdin sync script\n')

print('STEP 1: Create cm_caf.xml')

if not os.path.isfile('caf.xml'):
    sys.exit('You have no caf.xml. Terminating')
xml = minidom.parse('caf.xml')
items = xml.getElementsByTagName('item')

cm_caf = []

for item in items:
    call(['mkdir', '-p', 'tmp/' + item.attributes["path"].value])
    item_aosp = item.getElementsByTagName('aosp')
    for aosp_item in item_aosp:
        url = aosp_item.firstChild.nodeValue
        path_to_base = 'tmp/' + item.attributes["path"].value + '/' + aosp_item.attributes["file"].value
        path_to_cm = item.attributes["path"].value + '/' + aosp_item.attributes["file"].value
        path = item.attributes["path"].value
        urlretrieve(url, path_to_base)
        cm_sync.create_cm_caf_xml(path_to_base, path_to_cm, path)
        cm_caf.append(path + '/cm_caf.xml')

print('\nSTEP 2: Upload Crowdin source translations')

print('\nSTEP 3: Clean up')
for cm_caf_file in cm_caf:
    print ('Removing ' + cm_caf_file)
    os.remove(cm_caf_file)

print('\nSTEP 4: Done!')
