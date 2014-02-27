#!/usr/bin/python2

from xml.dom import minidom

def create_cm_caf_xml(strings_base, strings_cm, path):
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
            names_cm_string-array.append(s.attributes['name'].value)
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

    # Search for different names. If so, output the full line
    t = 5

    for z in names_cm_string:
        if not z in names_base_string:
            if t == 5:
                f = open(path + '/cm_caf.xml','w')
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                f.write('<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n')
                t = 4
            f.write(list_cm_string[names_cm_string.index(z)].toxml() + '\n')
    for z in names_cm_string_array:
        if not z in names_base_string_array:
            if t == 5:
                f = open(path + '/cm_caf.xml','w')
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                f.write('<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n')
                t = 4
            f.write(list_cm_string_array[names_cm_string_array.index(z)].toxml() + '\n')
    for z in names_cm_plurals:
        if not z in names_base_plurals:
            if t == 5:
                f = open(path + '/cm_caf.xml','w')
                f.write('<?xml version="1.0" encoding="utf-8"?>\n')
                f.write('<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n')
                t = 4
            f.write(list_cm_plurals[names_cm_plurals.index(z)].toxml() + '\n')

    if t == 4:
        f.write('</resources>')
        f.close()
