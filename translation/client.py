#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# client.py
#
# Derived class for the CrowdinClient so we can default some parameters
# and work around an issue
#
# Copyright (C) 2025 The LineageOS Project
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

from crowdin_api import CrowdinClient

import utils


class TranslationClient(CrowdinClient):
    TOKEN = utils.get_access_token()
    TIMEOUT = 60
    RETRY_DELAY = 0.1
    MAX_RETRIES = 5
    PAGE_SIZE = 25

    # Workaround an exception occurring after script end
    def __del__(self):
        pass
