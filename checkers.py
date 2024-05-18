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
import sys
import os
import platform
import time
from urllib.parse import urljoin
import logging
from utils import chk_or_obtain, run_process

LOGGER = logging.getLogger(__name__)


def chk_files_cache(d_files_db: dict[str, Any], l_kind: list[str],
                    l_type: list[str], b_mist: bool, l_tags: list[str],
                    s_files_path: str, b_force: bool):
    """
    Populates files disk cache, checking the existing ones and downloading when
    needed
    :param d_files_db: Dict with files DB
    :param l_kind: List of kind of core files to populate/check (e.g. a200t)
    :param l_type: List of type of core files (e.g. bit, zx3)
    :param b_mist: True if mist mode is active
    :param l_tags: List with tags that apply
    :param s_files_path: Path for the files cache
    :param b_force: If True, delete (if exists) and download again
    :return: Nothing
    """

    d_files: dict[str, Any] = d_files_db.get('files', {})
    d_tags: dict[str, Any] = d_files_db.get('tag_dictionary', {})

    if b_mist:
        l_kind = ['a35t', 'a100t', 'a200t']

    for s_file in d_files:
        s_name: str = s_file.split('/')[-1]

        b_download: bool = True  # If there are no tags, download always
        if d_tags:
            b_download = False
            s_kind = d_files[s_file].get('kind', '')
            if s_kind in l_kind and d_files[s_file].get(
                    'type', None) in l_type:  # Fully tagged
                b_download = True
            elif not s_kind:  # Partial tag, download always
                b_download = True

        if b_download:
            if d_tags:
                b_download = False
                for i_item in d_files[s_file]['tags']:
                    for j_item in d_tags:
                        if d_tags[j_item] == i_item and j_item in l_tags:
                            b_download = True

            if b_download:
                s_file_path: str = s_files_path
                l_files_subpath: list[str] = d_files[s_file].get('path', [])
                if l_files_subpath:
                    s_file_path = os.path.join(s_file_path,
                                               os.path.join(*l_files_subpath))
                b_ok: bool = chk_or_obtain(os.path.join(s_file_path, s_name),
                                           d_files[s_file]['hash'],
                                           d_files[s_file]['size'],
                                           d_files[s_file]['url'],
                                           b_force=b_force)
                if not b_ok:
                    print(f'{s_name} Bad file!')


def chk_zip_cache(d_arcade_db: dict[str, Any], d_cores_db: dict[str, Any],
                  s_roms_path: str, b_force: bool):
    """
    Populates ROM ZIP files disk cache
    :param d_arcade_db: Dict with arcade DB
    :param d_cores_db: Dict with cores DB
    :param s_roms_path: Path for the ROM files cache
    :param b_force: If True, delete (if exists) and download again
    :return: Nothing
    """

    d_files: dict[str, Any] = d_arcade_db['files']
    d_tags: dict[str, Any] = d_arcade_db['tag_dictionary']

    for s_file in d_files:
        s_name: str = s_file.split('/')[-1]
        for i_item in d_files[s_file]['tags']:
            for j_item in d_tags:
                if d_tags[j_item] == i_item and j_item in d_cores_db:
                    b_ok: bool = chk_or_obtain(os.path.join(
                        s_roms_path, s_name),
                                               d_files[s_file]['hash'],
                                               d_files[s_file]['size'],
                                               d_files[s_file]['url'],
                                               b_force=b_force)
                    if not b_ok:
                        print(f'{s_name} Bad file!')


def chk_mra_cache(d_mra_db: dict[str, Any], d_cores_db: dict[str, Any],
                  s_mras_path: str, b_force: bool,
                  s_baseurl: str) -> dict[str, Any]:
    """
    Populates MRA text files disk cache
    :param d_mra_db: Dict with MRA DB
    :param d_cores_db: Dict with cores DB
    :param s_mras_path: Path for the MRA files cache
    :param b_force: If True, delete existing files and download again
    :param s_commit: If not empyt, commit id to use to download the MRA files
    :return: Dict with MRA groups info
    """

    d_mras: dict[str, Any] = {}
    d_files: dict[str, Any] = d_mra_db['files']
    d_tags: dict[str, Any] = d_mra_db['tag_dictionary']
    for s_file in d_files:
        s_name: str = s_file.split('/')[-1]
        if s_name.endswith('.mra') and not '_alternatives' in s_file:
            for s_item in d_files[s_file]['tags']:
                for s_tagitem in d_tags:
                    if d_tags[s_tagitem] == s_item and ''.join(
                            s_tagitem.split('arcade')) in d_cores_db:
                        if not s_tagitem in d_mras:
                            d_mras[s_tagitem] = []
                        d_mras[s_tagitem].append(s_name)
                        s_url: str = s_baseurl + s_name
                        if 'url' in d_files[s_file]:
                            s_url = d_files[s_file]['url']
                        b_ok = chk_or_obtain(os.path.join(s_mras_path, s_name),
                                             d_files[s_file]['hash'],
                                             d_files[s_file]['size'],
                                             s_url,
                                             b_force=b_force)
                        if not b_ok:
                            print(f'{s_name} Bad file!')

    return d_mras


def chk_or_download_autoboot(s_autobootbin: str,
                             s_autoboot_path: str,
                             b_force: bool = False) -> bool:
    """
    Download autoboot BAS file if does not exist
    :param s_autobootbin: File name
    :param s_autoboot_path: Path to dir where the file should be
    :param b_force: If True, delete an existing file and download again
    :return: True if the file exists or is downloaded
    """

    b_ok: bool = True
    s_autobootbin_binurl: str = 'https://github.com/kounch/ZX3_Downloader/raw/'
    s_autobootbin_binurl += '2dc6cdc411c744aa9db20dfbd616bef299770af2/Autoboot/'
    d_autoboot: dict[str, tuple[str, int]] = {
        'AUTOBOOT_BIT.BAS': ('58411f0a0c5f48adf6935734ad0ae63b', 337),
        'AUTOBOOT_CORES.BAS': ('f780a4a6209f700594e9f5c2fbaae42b', 333),
        'AUTOBOOT_ZX3.BAS': ('10731bb09ec48e11596249c10905b942', 337),
        'AUTOBOOT_MIST.BAS': ('46e2c93f6479eddc568c5e254a98a8c5', 332)
    }
    s_binhash: str = d_autoboot[s_autobootbin][0]
    i_binsize: int = d_autoboot[s_autobootbin][1]

    s_binpath: str = os.path.join(s_autoboot_path, s_autobootbin)
    s_binurl: str = urljoin(s_autobootbin_binurl, s_autobootbin)

    if not os.path.isfile(s_binpath):
        b_ok = chk_or_obtain(s_binpath,
                             s_url=s_binurl,
                             s_hash=s_binhash,
                             i_size=i_binsize,
                             b_force=b_force)
    return b_ok


def chk_or_download_mrabin(s_mrabin_dirpath: str,
                           b_force: bool = False) -> str:
    """
    Download mra binary file if does not exist
    :param s_mra_dirpath: Path to dir where the file should be
    :param b_force: If True, delete an existing file and download again
    :return: String with the full path to the binary file
    """

    b_ok: bool = True

    s_mra_binname: str = 'mra'
    s_mra_binurl: str = 'https://github.com/kounch/mra-tools-c/raw/master/release/'

    if sys.platform == 'darwin':
        s_mra_binurl = urljoin(s_mra_binurl, 'macos/')
    elif sys.platform == 'win32':
        s_mra_binurl = urljoin(s_mra_binurl, 'windows/')
        s_mra_binname = 'mra.exe'
    else:  # Assume Linux
        s_mra_binurl = urljoin(s_mra_binurl, 'linux/')
        if platform.machine() == 'armv7l':
            s_mra_binname = 'mra.armv7l'
        elif platform.machine() == 'aarch64':
            s_mra_binname = 'mra.aarch64'

    s_mra_binpath: str = os.path.join(s_mrabin_dirpath, s_mra_binname)
    s_mra_binurl = urljoin(s_mra_binurl, s_mra_binname)

    if not os.path.isfile(s_mra_binpath):
        b_ok = chk_or_obtain(s_mra_binpath,
                             s_url=s_mra_binurl,
                             b_force=b_force)
        time.sleep(15)  # Give Windows some time to check the file
        if sys.platform != 'win32':
            run_process(['chmod', 'a+x', s_mra_binpath], 'mra tool binary')
        if not b_ok:
            s_mra_binpath = ''

    return s_mra_binpath
