#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
# Do not modify previous lines. See PEP 8, PEP 263.
"""
Copyright (c) 2023-2024, kounch
All rights reserved.

SPDX-License-Identifier: BSD-2-Clause
"""

from __future__ import annotations
from typing import Any
import pathlib
import os
import json
from zipfile import ZipFile, is_zipfile
from urllib.parse import urljoin
import hashlib
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, quote, unquote, ParseResult
import shutil
from subprocess import run, CompletedProcess
import logging

LOGGER = logging.getLogger(__name__)


def load_db(s_dirpath: str,
            s_name: str,
            s_urlbase: str = '',
            s_hash: str = '',
            i_size: int = 0,
            b_force: bool = False) -> dict[str, Any]:
    """
    Loads Database from JSON or from JSON inside ZIP file
    :param s_dirpath: Directory where the file should be
    :param s_name: JSON file name
    :param s_urlbase: Base URL to compose the path to download
    :param s_hash: Hash of ZIP file
    :param i_size: Size of ZIP file
    :param b_force: If True, delete an existing file and download again
    :return: Dictionary with data
    """

    s_zipname: str = s_name + '.zip'
    s_dirpath = os.path.join(s_dirpath, 'db')
    s_json: str = os.path.join(s_dirpath, s_name)
    s_jsonzip: str = os.path.join(s_dirpath, s_zipname)

    if b_force and os.path.isfile(s_jsonzip):
        os.remove(s_jsonzip)

    if not os.path.isfile(s_json):
        b_ok: bool = chk_or_obtain(s_jsonzip, s_hash, i_size,
                                   urljoin(s_urlbase, s_zipname))
        if not b_ok:
            print(f'{s_name} Bad file!')

    d_result: dict[str, Any] = {}
    if os.path.isfile(s_json):
        with open(s_json, 'r', encoding='utf-8') as json_handle:
            LOGGER.debug('Loading database...')
            d_result = json.load(json_handle)
    elif is_zipfile(s_jsonzip):
        with ZipFile(s_jsonzip, "r") as z_handle:
            for s_filename in z_handle.namelist():
                if s_filename == s_name:
                    LOGGER.debug('Loading Arcade DB %s...', s_jsonzip)
                    with z_handle.open(s_filename) as json_handle:
                        json_data: bytes = json_handle.read()
                        d_result = json.loads(json_data.decode("utf-8"))
                    break
    else:
        print(f'{s_name} Not found or not in a ZIP file!')

    return d_result


def chk_or_obtain(s_fpath: str,
                  s_hash: str = '',
                  i_size: int = 0,
                  s_url: str = '',
                  s_zip_path: str = '',
                  s_orig: str = '',
                  b_force: bool = False) -> bool:
    """
    Download a file from a URL or extract a file from inside a ZIP archive if
    it does not exist and, optionally, check hash and size
    :param s_fpath: File path of the obtained file
    :param s_hash: MD5 hash to check
    :param i_size: Size (bytes) to check
    :param s_url : Optional URL to download from
    :param s_zip_path: Path to the ZIP archive file
    :param s_orig: Path to where the file should be inside the ZIP archive
    :param b_force: If True, delete an existing file and download again
    :return: Boolean indicating download or extraction, check, etc. where all ok
    """

    b_ok: bool = True

    s_name: str = s_fpath.split('/')[-1]
    s_path: str = os.path.dirname(s_fpath)
    if not os.path.isdir(s_path):
        pathlib.Path(s_path).mkdir(parents=True, exist_ok=True)

    if b_force and os.path.isfile(s_fpath):
        os.remove(s_fpath)

    b_ok = chk_file_hash(s_fpath, s_hash, i_size, s_name)
    if not b_ok and os.path.isfile(s_fpath):
        LOGGER.debug('%s wrong hash. Replacing...', s_name)
        os.remove(s_fpath)

    if not os.path.isfile(s_fpath):
        if s_url != '':
            print(f'Downloading {s_name}...')
            s_turl: str = unquote(s_url, encoding='utf-8', errors='replace')
            if len(s_turl) == len(s_url):
                urlparse_t: ParseResult = urlparse(s_url)
                s_url = urlparse_t.scheme + "://" + urlparse_t.netloc + quote(
                    urlparse_t.path)
                if urlparse_t.query != '':
                    s_url += "?" + quote(urlparse_t.query)

            try:
                urllib.request.urlretrieve(s_url, s_fpath)
            except HTTPError as error:
                LOGGER.debug('Cannot fetch %s! %s', s_url, error)
            except URLError as error:
                LOGGER.error('Connection error: %s! %s', s_url, error)
                b_ok = False
        elif s_zip_path != '':
            LOGGER.debug('Extracting %s...', s_orig)
            with ZipFile(s_zip_path, "r") as z_handle:
                with z_handle.open(s_orig) as member:
                    with open(s_fpath, 'wb') as outfile:
                        shutil.copyfileobj(member, outfile)
                    b_ok = True
        else:
            LOGGER.error('%s not found!', s_name)
            b_ok = False

    b_ok = chk_file_hash(s_fpath, s_hash, i_size, s_name)
    if not b_ok:
        LOGGER.error('Could not obtain file: %s!', s_name)

    return b_ok


def chk_file_hash(s_fpath: str, s_hash: str, i_size: int, s_name: str) -> bool:
    """
    Check file hash and size if it exists
    :param s_fpath: File path of the obtained file
    :param s_hash: MD5 hash to check
    :param i_size: Size (bytes) to check
    :param s_name: Text to show filename on errors and logs
    :return: True if file exists, hash and size are correct
    """

    b_ok: bool = True
    if os.path.isfile(s_fpath):
        if s_hash != '' and i_size != 0:
            i_fsize: int = os.stat(s_fpath).st_size
            LOGGER.debug('%s obtained, checking...', s_name)
            s_hashcheck: str = get_file_hash(s_fpath)
            if s_hash != s_hashcheck or i_fsize != i_size:
                LOGGER.debug('%s wrong file!', s_name)
                b_ok = False
    else:
        b_ok = False

    return b_ok


def get_file_hash(str_in_file: str) -> str:
    """
    Get file md5 hash
    :param str_in_file: Path to file
    :return: String with hash data
    """

    md5_hash: object = hashlib.md5()
    with open(str_in_file, "rb") as f_data:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f_data.read(4096), b""):
            md5_hash.update(byte_block)

    return md5_hash.hexdigest()


def run_process(l_mra_params: list[str], s_item: str):
    """
    Runs a process, printing stdout, and logging an errir if stderr not empty
    :param l_mra_params: list of command line command and parameters
    :param s_item: Text to show as element in error if stderr not empty
    :return: Nothing
    """

    my_process: CompletedProcess[Any] = run(l_mra_params,
                                            capture_output=True,
                                            check=False,
                                            encoding='utf8')
    if my_process.stdout != '':
        LOGGER.debug(my_process.stdout)
    if my_process.stderr != '':
        LOGGER.error('Problem processing %s: %s', s_item, my_process.stderr)
