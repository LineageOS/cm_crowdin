#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# utils.py
#
# Helper script to get crowdin information for the wiki
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

import os
import requests

import utils

crowdin_url = "https://api.crowdin.com/api/v2/projects"
token = None


# These people are global proofreaders / managers and wouldn't appear for their languages otherwise
users_to_append = {
    "it": {
        "name": "Italian",
        "users": [{"username": "linuxx", "fullName": "Joey Rizzoli"}],
    },
    "de": {
        "name": "German",
        "users": [
            {"username": "maniac103", "fullName": "Danny Baumann"},
            {"username": "BadDaemon", "fullName": "Michael W"},
        ],
    },
    "nl": {
        "name": "Dutch",
        "users": [{"username": "eddywitkamp", "fullName": "Eddy Witkamp"}],
    },
    "en-pt": {
        "name": "Pirate English",
        "users": [{"username": "javelinanddart", "fullName": "Paul Keith"}],
    },
    "en-AU": {
        "name": "English, Australia",
        "users": [{"username": "forkbomb", "fullName": "Simon Shields"}],
    },
    "el": {
        "name": "Greek",
        "users": [{"username": "mikeioannina", "fullName": "Michael Bestas"}],
    },
}


def generate_proofreader_list(config_files):
    print("\nGenerating proofreader list")
    t = utils.start_spinner(True)

    ids = get_project_ids(config_files)
    languages = get_languages(ids)
    proofreaders = get_proofreaders(ids, languages)

    proofreaders_final = {}
    for p in proofreaders:
        if len(proofreaders[p]["users"]) == 0:
            continue
        proofreaders_final.setdefault(proofreaders[p]["name"], proofreaders[p]["users"])

    utils.stop_spinner(t)
    print("\n")
    for p in sorted(proofreaders_final):
        names = []
        for u in proofreaders_final[p]:
            if u["fullName"] is not None and len(u["fullName"]) > 0:
                names.append(f"'{u['fullName']} ({u['username']})'")
            else:
                names.append(f"'{u['username']}'")
        print(f"- name: {p}")
        print(f"  proofreaders: [{', '.join(names)}]")
    exit()


def get_project_ids(config_files):
    ids = []
    for f in config_files:
        with open(f, "r") as fh:
            for line in fh.readlines():
                if "project_id" in line:
                    ids.append(int(line.strip("\n").split(": ")[1]))
    return ids


def get_from_api(url):
    resp = requests.get(url, headers=get_headers())
    if resp.status_code != 200:
        print(f"Error retrieving data - {resp.json()}")
        exit()
    return resp.json()


def get_languages(project_ids):
    languages = {}
    for project_id in project_ids:
        json = get_from_api(f"{crowdin_url}/{project_id}")
        target_languages = json["data"]["targetLanguages"]
        for lang in target_languages:
            languages.setdefault(lang["id"], {"name": lang["name"], "users": []})
    return languages


def get_headers():
    global token
    if token is None:
        get_access_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    return headers


def get_access_token():
    global token
    token = os.getenv("LINEAGE_CROWDIN_API_TOKEN")
    if token is None:
        print(
            "Could not determine api token, please export LINEAGE_CROWDIN_API_TOKEN to the environment!"
        )
        exit(-1)


def get_proofreaders(project_ids, languages):
    for project_id in project_ids:
        for language in languages:
            members = get_from_api(
                f"{crowdin_url}/{project_id}/members?role=proofreader&languageId={language}"
            )
            for data in members["data"]:
                if "permissions" not in data["data"]:
                    continue
                user = {
                    "username": data["data"]["username"],
                    "fullName": data["data"]["fullName"],
                }
                # We might have the same user in several projects, only add them once
                if user not in languages[language]["users"]:
                    languages[language]["users"].append(user)
            for user in users_to_append:
                if user not in languages:
                    continue
                for u in users_to_append[user]["users"]:
                    if u not in languages[user]["users"]:
                        languages[user]["users"].append(u)
    return languages
