#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# download.py
#
# Helper script for downloading translation source and
# uploading it to LineageOS' gerrit
#
# Copyright (C) 2022 The LineageOS Project
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
import sys
import zipfile
from zipfile import ZipFile

import download


def unzip(zip_files, base_path, branch, xml, username):
    print("\nUnzipping files")
    extracted = []
    number = 1

    for zip_file in zip_files:
        if not zipfile.is_zipfile(zip_file):
            print(
                f"WARNING: Specified file is not a valid zip file, skipping '{zip_file}'"
            )
            continue

        print(f"File {number}/{len(zip_files)}")
        with ZipFile(zip_file, "r") as my_zip:
            files = my_zip.namelist()
            my_zip.extractall(path=base_path)
        extracted += [x for x in files if x.endswith(".xml") and x not in extracted]
        number += 1

    download.upload_translations_gerrit(extracted, xml, base_path, branch, username)
