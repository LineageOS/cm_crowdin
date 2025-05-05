#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# verify.py
#
# Script to download and verify all approved translations
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

import io
import logging
import os
import tempfile
import time
import zipfile

import requests
from datetime import datetime, timedelta

import download
import utils
from CrowdinParams import CrowdinParams
from translation.client import TranslationClient


def verify_translations(crowdin_config: CrowdinParams):
    try:
        client = TranslationClient()
        build_ids = start_all_builds(client, crowdin_config)
        build_results = wait_for_builds(client, build_ids)

        if not check_build_success(build_results):
            logging.error("One or more project builds failed.")
            exit(-1)

        logging.info("All project builds succeeded.")

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            download_builds(client, build_ids, tmp_dir_name)
            verify_files(tmp_dir_name)
    finally:
        del client


def start_all_builds(client, crowdin_config: CrowdinParams):
    project_ids = utils.get_project_ids(crowdin_config.config_dict["files"])
    build_ids = {}
    for project_id in project_ids:
        branch_id = get_branch_id(client, project_id, crowdin_config.branch)
        build_ids[project_id] = start_single_build(client, project_id, branch_id)
    return build_ids


def get_branch_id(client, project_id, branch_name):
    logging.info(
        f"Getting branch id for project {project_id} and branch '{branch_name}'"
    )

    try:
        response = client.source_files.list_project_branches(
            projectId=project_id, name=branch_name
        )
        if response and response.get("data") and response["data"][0].get("data"):
            return response["data"][0]["data"]["id"]
    except Exception as e:
        logging.exception(f"Failed to list project branches: {e}")
        exit(-1)

    logging.error(
        f"Failed to get branch id for project {project_id} and branch '{branch_name}'"
    )
    exit(-1)


def start_single_build(client, project_id, branch_id):
    response = client.translations.build_crowdin_project_translation(
        projectId=project_id,
        branchId=branch_id,
        skipUntranslatedStrings=True,
        exportApprovedOnly=True,
    )
    data = response.get("data", [])
    if data and data.get("id"):
        return data["id"]

    return None


def wait_for_builds(client, build_ids, timeout=300):
    spinner = utils.start_spinner(show_spinner=True)
    build_results = wait_for_multiple_builds(client, build_ids, timeout)
    utils.stop_spinner(spinner)
    return build_results


def wait_for_multiple_builds(
    client, project_build_ids, timeout_seconds=60, poll_interval_seconds=5
):
    logging.info(
        f"Waiting for builds: {project_build_ids} to complete (timeout: {timeout_seconds}s)"
    )

    start_time = datetime.now()
    active_builds = set(project_build_ids.keys())
    build_statuses = {}

    timeout = timedelta(seconds=timeout_seconds)
    while active_builds and datetime.now() - start_time < timeout:
        projects_to_remove = set()
        for project_id in list(active_builds):  # Iterate over a copy to allow removal
            build_id = project_build_ids[project_id]
            try:
                response = client.translations.check_project_build_status(
                    buildId=build_id, projectId=project_id
                )
                status_data = response.get("data")
                if status_data:
                    status = status_data.get("status")
                    progress = status_data.get("progress")
                    logging.info(
                        f"Project {project_id}, Build {build_id} status: {status}, progress: {progress}%"
                    )
                    build_statuses[project_id] = status_data
                    if status == "finished" and progress == 100:
                        logging.info(
                            f"Project {project_id}, Build {build_id} completed."
                        )
                        projects_to_remove.add(project_id)
                    elif status == "failed":
                        logging.error(f"Project {project_id}, Build {build_id} failed.")
                        projects_to_remove.add(project_id)
                else:
                    logging.warning(
                        f"Received empty data for Project {project_id}, Build {build_id}."
                    )
            except Exception as e:
                logging.error(
                    f"Error checking build status for Project {project_id}, Build {build_id}: {e}"
                )
                build_statuses[project_id] = None
                projects_to_remove.add(project_id)

        active_builds -= projects_to_remove
        if active_builds:
            time.sleep(poll_interval_seconds)

    if active_builds:
        logging.warning(
            f"Timeout reached while waiting for builds: {active_builds} to complete."
        )
        # Ensure an entry for timed out builds
        for project_id in active_builds:
            build_statuses[project_id] = build_statuses.get(project_id) or None

    return build_statuses


def check_build_success(build_results):
    for project_id, status_data in build_results.items():
        if (
            not status_data
            or status_data.get("status") != "finished"
            or status_data.get("progress") != 100
        ):
            status = status_data.get("status") if status_data else "Error/Timeout"
            logging.error(
                f"Project {project_id} build did not succeed. Status: {status}"
            )
            return False
    return True


def download_builds(client, build_ids, tmpdir):
    logging.info("Downloading builds")

    links = get_download_links(client, build_ids)
    for link in links:
        r = requests.get(link)
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z.extractall(tmpdir)


def verify_files(dir_name):
    wrong_strings = 0
    for dir_path, dir_names, filenames in os.walk(dir_name):
        for filename in filenames:
            if filename.lower().endswith(".xml"):
                filepath = os.path.join(dir_path, filename)
                result = download.clean_xml_file(filepath)
                if result:
                    wrong_strings += result

    if wrong_strings > 0:
        logging.error(f"Found {wrong_strings} invalid strings, verification failed")
        exit(-1)

    logging.info("Verification succeeded!")


def get_download_links(client, build_ids):
    links = []
    for project_id in build_ids:
        build_id = build_ids[project_id]
        try:
            response = client.translations.download_project_translations(
                projectId=project_id, buildId=build_id
            )
            download_data = response.get("data")
            if download_data:
                links.append(download_data.get("url"))
        except Exception as e:
            logging.error(
                f"Error getting download for Project {project_id}, Build {build_id}: {e}"
            )
            exit(-1)
    return links
