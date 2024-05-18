#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- mode: Python; tab-width: 4; indent-tabs-mode: nil; -*-
# Do not modify previous lines. See PEP 8, PEP 263.
"""
Copyright (c) 2023-2024, kounch
All rights reserved.

SPDX-License-Identifier: BSD-2-Clause
"""

from __future__ import print_function
from __future__ import annotations
from typing import Any
import logging
import sys
import platform
import argparse
import pathlib
import os
import json
import hashlib
import ssl
from zipfile import ZipFile, is_zipfile
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, quote, unquote, urljoin, ParseResult
import socket
import shutil
from subprocess import run, CompletedProcess
import time

__MY_VERSION__ = '1.2.0'

MY_BASEPATH: str = os.path.dirname(sys.argv[0])
MY_DIRPATH: str = os.path.abspath(MY_BASEPATH)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
LOG_FORMAT = logging.Formatter(
    '%(asctime)s [%(levelname)-5.5s] - %(name)s: %(message)s')
LOG_STREAM = logging.StreamHandler(sys.stdout)
LOG_STREAM.setFormatter(LOG_FORMAT)
LOGGER.addHandler(LOG_STREAM)

if sys.version_info < (3, 7, 0):
    LOGGER.error('This software requires Python version 3.7 or greater')
    sys.exit(1)

ssl._create_default_https_context = ssl._create_unverified_context  # pylint: disable=protected-access
socket.setdefaulttimeout(900)


def main():
    """Main routine"""

    arg_data: dict[str, Any] = parse_args()

    s_cache_path: str = arg_data['cache_dir']
    s_out_path: str = arg_data['out_dir']

    if arg_data['clean_sd']:
        print('Cleaning SD path...')
        if os.path.isdir(s_out_path):
            shutil.rmtree(s_out_path)

    print('Checking Main DB...')
    s_urlbase: str = 'https://github.com/kounch/ZX3_Downloader/raw/bd/'
    d_main_db: dict[str, Any] = load_db(s_cache_path,
                                        'zx3_main_db.json',
                                        s_urlbase,
                                        b_force=not arg_data['keep'])
    if not d_main_db:
        LOGGER.error('Unable to obtain main DB file...')
        sys.exit(2)

    d_tags: dict[str, Any] = d_main_db['tag_dictionary']
    for s_pack, d_pack in d_main_db['packs'].items():
        LOGGER.debug('Processing %s', s_pack)
        b_do_pack: bool = True
        if d_pack['tags']:
            b_do_pack = False
            for i_tg in d_tags:
                if d_tags[i_tg] in d_pack['tags'] and i_tg in arg_data['tags']:
                    b_do_pack = True
                    break

        if b_do_pack:
            b_ok: bool = False
            if d_pack["type"] == "zip":
                print(f'Checking/Building {d_pack["name"]} files from ZIP...')
                b_ok = build_sd_zip_fromdb(s_cache_path, d_pack, arg_data)
            elif d_pack["type"] == "files":
                print(f'Checking/Building {d_pack["name"]} files...')
                b_ok = build_sd_files_fromdb(s_cache_path, d_pack, arg_data)
            elif d_pack["type"] == "arcade":
                print(f'Checking/Building {d_pack["name"]}:')
                b_ok = build_arcade_sd_fromdb(s_cache_path, d_pack, s_out_path)
            if not b_ok:
                LOGGER.error("Error building %s files", d_pack["name"])

    # TMP for esxdos
    s_tmp_path: str = os.path.join(s_out_path, 'TMP')
    if not os.path.isdir(s_tmp_path):
        pathlib.Path(s_tmp_path).mkdir(parents=True, exist_ok=True)

    # Autotoboot for esxdos
    if arg_data['autoboot']:
        b_ok = build_autoboot(os.path.join(MY_DIRPATH, 'Autoboot'),
                              arg_data['autoboot'], s_out_path)

    # Extra content
    if arg_data['extra_dir']:
        if os.path.isdir(arg_data['extra_dir']):
            print(f'Copying extra files from {arg_data["extra_dir"]}...')
            copy_extra_files(pathlib.Path(arg_data['extra_dir']),
                             pathlib.Path(arg_data['extra_dir']),
                             pathlib.Path(s_out_path))

    print("Finished")


def copy_extra_files(base_path: pathlib.Path, input_path: pathlib.Path,
                     dest_path: pathlib.Path):
    """
    Recursive analysis of files and directories
    :param base_path: Path to take as base to get relative directories
    :param input_path: Path to analyze (subpath of base_path)
    :dest_dir: Path of destination directory
    """

    if input_path.is_dir():
        try:
            for child in input_path.iterdir():
                chld_path: pathlib.Path = pathlib.Path(base_path, input_path,
                                                       child)
                if chld_path.is_file():
                    copy_extra_file(base_path, chld_path, dest_path)
                elif chld_path.is_dir():
                    copy_extra_files(base_path, chld_path, dest_path)
        except PermissionError:
            LOGGER.error('Permission Error on %s', input_path)
    else:
        copy_extra_file(base_path, input_path, dest_path)


def copy_extra_file(base_path: pathlib.Path, input_file: pathlib.Path,
                    dest_dir: pathlib.Path):
    """
    Analyze file paths and try to copy
    :param base_path: Path to take as base to get relative directories
    :param input_file: Path of file to copy (subpath of base_path)
    :dest_dir: Path of destination directory
    """

    s_path: str = str(input_file).split(str(base_path))[1]
    s_fpath: str = str(dest_dir) + s_path
    s_path: str = os.path.dirname(s_fpath)
    if not os.path.isdir(s_path):
        pathlib.Path(s_path).mkdir(parents=True, exist_ok=True)
    LOGGER.debug('Copy %s to %s', input_file, dest_dir)
    try:
        shutil.copyfile(input_file, s_fpath)
    except OSError as err:
        LOGGER.error(err)


def parse_args() -> dict[str, Any]:
    """
    Parses command line
    :return: Dictionary with different options
    """
    global LOGGER  # pylint: disable=global-variable-not-assigned

    values: dict[str, Any] = {}
    values['clean_sd'] = False
    values['cache_dir'] = os.path.join(MY_DIRPATH, 'cache')
    values['out_dir'] = os.path.join(MY_DIRPATH, 'SD')
    values['extra_dir'] = os.path.join(MY_DIRPATH, 'extra')
    values['kinds'] = []
    values['types'] = ['bit', 'zx3']
    values['mist_mode'] = False
    values['tags'] = ['arcade', 'console', 'computer', 'util']
    values['group_types'] = False
    values['group_tags'] = False
    values['keep'] = False
    values['autoboot'] = 'cores'

    parser = argparse.ArgumentParser(description='ZX3 Downloader',
                                     epilog='Downloads files for ZX3 microSD')
    parser.add_argument('-v',
                        '--version',
                        action='version',
                        version=f'%(prog)s {__MY_VERSION__}')

    parser.add_argument('-c',
                        '--clean_sd',
                        required=False,
                        action='store_true',
                        dest='clean_sd',
                        help='Make a clean build of the SD')

    parser.add_argument('-C',
                        '--cache_dir',
                        required=False,
                        action='store',
                        dest='cache_dir',
                        help='Cache directory name and location')

    parser.add_argument('-O',
                        '--out_dir',
                        required=False,
                        action='store',
                        dest='out_dir',
                        help='Output directory name and location')

    parser.add_argument('-E',
                        '--extra_dir',
                        required=False,
                        action='store',
                        dest='extra_dir',
                        help='Extra directory name and location')

    parser.add_argument('-K',
                        '--keep',
                        required=False,
                        action='store_true',
                        dest='keep',
                        help='Keep previous existing files and directories')

    parser.add_argument('-k',
                        '--kinds',
                        required=True,
                        action='append',
                        dest='kinds',
                        help='List of kinds of fpgas to include')

    parser.add_argument('-t',
                        '--types',
                        required=False,
                        action='append',
                        dest='types',
                        help='List of types of core files to include')

    parser.add_argument('-m',
                        '--mode',
                        required=False,
                        action='store',
                        dest='mode',
                        help='Mode configuration (legacy or mist)')

    parser.add_argument('-T',
                        '--tags',
                        required=False,
                        action='append',
                        dest='tags',
                        help='List of tags to include')

    parser.add_argument('-g',
                        '--group_types',
                        required=False,
                        action='store_true',
                        dest='group_types',
                        help='Group core files by file type')

    parser.add_argument('-G',
                        '--group_tags',
                        required=False,
                        action='store_true',
                        dest='group_tags',
                        help='Group core files by tag')

    parser.add_argument('-a',
                        '--autoboot',
                        required=False,
                        action='store',
                        dest='autoboot',
                        help='Define autoboot type')

    parser.add_argument('-n',
                        '--no_autoboot',
                        required=False,
                        action='store_true',
                        dest='no_autoboot',
                        help='No autoboot install')

    parser.add_argument('--debug',
                        required=False,
                        action='store_true',
                        dest='debug')

    arguments = parser.parse_args()

    if arguments.debug:
        LOGGER.setLevel(logging.DEBUG)

    if arguments.clean_sd:
        values['clean_sd'] = arguments.clean_sd

    if arguments.cache_dir:
        values['cache_dir'] = os.path.abspath(arguments.cache_dir)

    if arguments.out_dir:
        values['out_dir'] = os.path.abspath(arguments.out_dir)

    if arguments.extra_dir:
        if os.path.isdir(arguments.extra_dir):
            values['extra_dir'] = os.path.abspath(arguments.extra_dir)
        else:
            LOGGER.error('Extra dir %s not found!', arguments.extra_dir)
            values['extra_dir'] = None

    if arguments.keep:
        values['keep'] = True

    if arguments.kinds:
        values['kinds'] = []
        all_kinds: list[str] = ['a35t', 'a100t', 'a200t']
        for s_kinds in arguments.kinds:
            l_kinds: list[str] = s_kinds.split(',')
            for s_kind in l_kinds:
                if s_kind.lower() in all_kinds:
                    values['kinds'].append(s_kind.lower())  # type: ignore
                else:
                    LOGGER.error('Bad kind of FPGA: %s', s_kind)

    if arguments.types:
        all_types: list[str] = values['types']
        values['types'] = []
        for s_types in arguments.types:
            l_types: list[str] = s_types.split(',')
            for s_type in l_types:
                if s_type.lower() in all_types:
                    values['types'].append(s_type.lower())  # type: ignore
                else:
                    LOGGER.error('Bad type of file: %s', s_type)

    if arguments.mode:
        l_modes = ['legacy', 'mist']
        if arguments.mode.lower() in l_modes:
            if arguments.mode.lower() == 'mist':
                values['mist_mode'] = True
            elif arguments.mode.lower() == 'legacy':
                values['mist_mode'] = False
        else:
            LOGGER.error('Bad mode: %s', arguments.mode)

    if arguments.tags:
        all_tags: list[str] = values['tags']
        values['tags'] = []
        for s_tags in arguments.tags:
            l_tags: list[str] = s_tags.split(',')
            for s_tag in l_tags:
                if s_tag.lower() in all_tags:
                    values['tags'].append(s_tag.lower())  # type: ignore
                else:
                    LOGGER.error('Bad tag: %s', s_tag)

    if arguments.group_types:
        values['group_types'] = True

    if arguments.autoboot:
        values['autoboot'] = arguments.autoboot

    l_boot_types: list[str] = ['cores']
    if values['mist_mode']:
        l_boot_types += ['mist']
    if values['group_types']:
        l_boot_types += values['types']

    if values['autoboot']:
        if values['autoboot'] not in l_boot_types:
            LOGGER.error('Bad boot type: %s', values['autoboot'])
            values['autoboot'] = ''

    if arguments.no_autoboot:
        values['autoboot'] = ''

    if arguments.group_tags:
        values['group_tags'] = True

    if not values['kinds']:
        LOGGER.error('Need at least one kind of FPGA')
        sys.exit(3)

    if not values['types']:
        LOGGER.error('Need at least one type of file')
        sys.exit(3)

    if not values['tags']:
        LOGGER.error('Need at least one valid tag')
        sys.exit(3)

    LOGGER.debug(values)
    return values


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


def build_sd_zip_fromdb(s_dir: str, d_db_params: dict[str, Any],
                        d_params: dict[str, Any]) -> bool:
    """
    Builds SD from ZIP file using DB of URLs, etc.
    :param s_dir: Path where DB file is to be found or downloaded
    :param d_db_params: Dictionary with all DB file info (hash, etc.)
    :param s_outdir: Base directory where the files are copied
    :return: Boolean indicating success
    """

    s_name: str = d_db_params['file']
    s_url: str = d_db_params['url']
    s_hash: str = d_db_params['hash']
    i_size: int = d_db_params['size']

    b_ok: bool = False

    LOGGER.debug('Checking %s ZIP DB...', s_name)
    d_db: dict[str, Any] = load_db(s_dir, s_name, s_url, s_hash, i_size, False)

    s_base_url: str = d_db.get('base_url', '')
    s_content: str = s_base_url.split('/')[-1]

    LOGGER.debug('Checking files (for %s DB)...', s_name)
    b_content: bool = chk_or_obtain(os.path.join(s_dir,
                                                 s_content), d_db['base_hash'],
                                    d_db['base_size'], s_base_url)
    if not b_content:
        LOGGER.error('Unable to obtain files for %s DB...', s_name)
        sys.exit(2)

    if s_content:
        LOGGER.debug('Copying files for SD from %s DB...', s_name)
        b_ok = build_sd_fromzip(d_db, d_params['kinds'], d_params['types'],
                                d_params['mist_mode'], d_params['tags'],
                                os.path.join(s_dir, s_content),
                                d_params['out_dir'], d_db_params['out_path'],
                                d_params['group_tags'],
                                d_params['group_types'])
    else:
        LOGGER.error('Content not defined in %s', s_name)

    return b_ok


def build_sd_files_fromdb(s_path: str, d_db_params: dict[str, Any],
                          d_params: dict[str, Any]) -> bool:
    """
    Builds SD downloading individual files using DB of URLs, etc.
    :param s_dir: Path where DB file is to be found or downloaded
    :param d_db_params: Dictionary with all DB file info (hash, etc.)
    :param d_params: Dictionary with global params (out dir, etc.)
    :return: Boolean indicating success
    """

    b_ok: bool = False

    s_json_db: str = d_db_params['file']
    s_name: str = d_db_params['path']
    s_url: str = d_db_params['url']
    s_hash: str = d_db_params['hash']
    i_size: int = d_db_params['size']
    s_out_path: str = d_db_params['out_path']
    b_keep: bool = True
    if d_db_params['args_keep']:
        b_keep = d_params['keep']
    b_force: bool = False

    s_files_path: str = os.path.join(s_path, s_name)
    d_files_db: dict[str, Any] = load_db(s_path, s_json_db, s_url, s_hash,
                                         i_size, b_force)
    if not d_files_db:
        LOGGER.error("There's no files JSON data for %s", s_json_db)
        sys.exit(2)

    LOGGER.debug('Checking Files Cache for %s...', s_json_db)
    chk_files_cache(d_files_db, d_params['kinds'], d_params['types'],
                    d_params['mist_mode'], d_params['tags'], s_files_path,
                    b_force)

    LOGGER.debug('Copying Files for SD...')
    b_ok = build_sd_files(d_files_db, d_params['kinds'], d_params['types'],
                          d_params['mist_mode'], d_params['tags'],
                          s_files_path, d_params['out_dir'], s_out_path,
                          d_params['group_tags'], d_params['group_types'],
                          b_keep)

    return b_ok


def build_sd_fromzip(d_zip_bd: dict[str, Any], l_kinds: list[str],
                     l_types: list[str], b_mist: bool, l_tags: list[str],
                     s_zip_path: str, s_out_path: str, s_out_subpath: str,
                     b_taggroups: bool, b_typegroups: bool) -> bool:
    """
    Builds SD extracting individual files according to filtering criteria
    :param d_zip_bd: Dictionary with all the ZIP files to extract
    :param l_kinds: Kind of core files to use (a100t, a35t, etc.)
    :param l_types: Type of core files to use (bit, zx3, etc.)
    :param b_mist: True if mist mode is active
    :param l_tags: Tags of the files to use (computer, arcade, etc.)
    :param s_zip_path: Full path to ZIP file containing original files
    :param s_out_path: Path where the files are to be copied
    :param s_out_subpath: Subpath of s_out_path to copy the files into
    :param b_taggroups: Group the files in directories by tag
    :param b_typegroups: Group the files in directories ty type
    :return: True if the extraction finishes without problems
    """

    b_ok = False
    d_zip_files: dict[str, Any] = d_zip_bd['files']
    d_tags: dict[str, Any] = d_zip_bd.get('tag_dictionary', {})

    if b_mist and s_out_subpath == 'cores':
        b_ok = build_zxt_sd_fromzip(d_zip_files, s_zip_path, s_out_path,
                                    'mist')
    for s_orig in d_zip_files:
        s_kind = d_zip_files[s_orig].get('kind', '')
        s_type: str = d_zip_files[s_orig].get('type', '')
        s_dest: str = s_out_path
        if s_out_subpath:
            if b_mist and s_out_subpath == 'cores' and s_type == 'bit':
                s_dest = os.path.join(s_dest, 'mist')
            else:
                s_dest = os.path.join(s_dest, s_out_subpath)
        l_subdirs: list[str] = d_zip_files[s_orig].get('path', [])
        if l_subdirs:
            s_dest: str = os.path.join(s_dest, os.path.join(*l_subdirs))

        s_hash: str = d_zip_files[s_orig]['hash']
        i_size: int = d_zip_files[s_orig]['size']
        if d_tags:
            if s_kind in l_kinds and s_type in l_types:  # Fully tagged item, copy if tag matches
                if b_typegroups and not (b_mist and s_type == 'bit'):
                    s_dest = os.path.join(s_dest, d_zip_files[s_orig]['type'])

                for i_item in d_zip_files[s_orig]['tags']:
                    for j_item in d_tags:
                        if d_tags[j_item] == i_item and j_item in l_tags:
                            if b_taggroups:
                                s_dest = os.path.join(s_dest, j_item)

                            if not os.path.isdir(s_dest):
                                pathlib.Path(s_dest).mkdir(parents=True,
                                                           exist_ok=True)
                            s_dest: str = os.path.join(
                                s_dest, d_zip_files[s_orig]['file'])
                            b_ok = chk_or_obtain(s_dest,
                                                 s_hash,
                                                 i_size,
                                                 s_zip_path=s_zip_path,
                                                 s_orig=s_orig)
        else:
            s_dest: str = os.path.join(s_dest, d_zip_files[s_orig]['file'])
            b_ok = chk_or_obtain(s_dest,
                                 s_hash,
                                 i_size,
                                 s_zip_path=s_zip_path,
                                 s_orig=s_orig)

    return b_ok


def build_zxt_sd_fromzip(d_zip_files: dict[str, Any], s_zip_path: str,
                         s_out_path: str, s_out_subpath: str) -> bool:
    """
    Tries to build ZXT core files for SD from ZIP file
    :param d_zip_files: Dictionary with all the ZIP files to extract
    :param s_zip_path: Full path to ZIP file containing original files
    :param s_out_path: Path where the files are to be copied
    :param s_out_subpath: Subpath of s_out_path to copy the core files into
    :return: True if files are built correctly
    """
    b_ok: bool = True
    s_kind = ''

    d_zxt: dict[str, dict[str, str]] = {}
    for s_file in d_zip_files:
        s_name: str = d_zip_files[s_file].get('file', '')
        s_kind: str = d_zip_files[s_file].get('kind', '')
        s_type: str = d_zip_files[s_file].get('type', '')
        if s_type == 'bit':
            s_zxtname: str = s_name.replace(s_kind, '').replace('__', '_')
            s_zxtname = s_zxtname.replace('_.', '.')
            if not s_zxtname in d_zxt:
                d_zxt[s_zxtname] = {}
            d_zxt[s_zxtname][s_kind] = s_file

    for s_core, d_bitfiles in d_zxt.items():
        if s_kind and s_kind in d_bitfiles and len(d_bitfiles) == 3:
            arr_bitfiles: list[str] = []
            for z_kind in ['a35t', 'a100t', 'a200t']:
                s_file: str = d_bitfiles.get(z_kind, '')
                arr_bitfiles.append(s_file)

            if len(arr_bitfiles) == 3:
                s_name: str = s_core.replace('.bit', '')
                s_sdpath = os.path.join(s_out_path, s_out_subpath)
                if not os.path.isdir(s_sdpath):
                    pathlib.Path(s_sdpath).mkdir(parents=True, exist_ok=True)
                s_sdpath: str = os.path.join(s_sdpath, f'{s_name}.zxt')

                arr_tmp: list[str] = []
                for s_orig in arr_bitfiles:
                    s_dest: str = f'{s_sdpath}_{s_orig}_tmp'
                    s_hash: str = d_zip_files[s_orig]['hash']
                    i_size: int = d_zip_files[s_orig]['size']
                    b_tok: bool = chk_or_obtain(s_dest,
                                                s_hash,
                                                i_size,
                                                s_zip_path=s_zip_path,
                                                s_orig=s_orig)
                    if b_tok:
                        arr_tmp.append(s_dest)
                if len(arr_tmp) == 3:
                    build_zxt_file(arr_tmp, s_sdpath)
                else:
                    b_ok = False

                for s_orig in arr_bitfiles:
                    s_dest = f'{s_sdpath}_{s_orig}_tmp'
                    if os.path.isfile(s_dest):
                        os.remove(s_dest)
                        del d_zip_files[s_orig]

    return b_ok


def build_arcade_sd_fromdb(s_dir: str, d_db_params: dict[str, Any],
                           s_outdir: str) -> bool:
    """
    Buils ARC and ROM files structure for arcade cores
    :param sdir: Cache base directory
    :param d_db_params: Dictionary with all DB file info (hash, etc.)
    :param s_outdir: Base directory where the files are created
    :return: True if everything is done correctly
    """
    s_roms_path: str = os.path.join(s_dir, 'roms')
    s_mras_path: str = os.path.join(s_dir, 'mra')

    l_arcade_dbs: list[str] = ['arcade_rom_db', 'mra_db', 'cores_db']
    d_arcade_dbs: dict[str, dict[str, Any]] = {}
    for db_key in l_arcade_dbs:
        db_value = d_db_params['dbs'][db_key]
        s_name: str = db_value['file']
        s_urlbase: str = db_value['url']
        s_hash: str = db_value['hash']
        i_size: int = db_value['size']
        d_arcade_dbs[db_key] = load_db(s_dir, s_name, s_urlbase, s_hash,
                                       i_size, False)
        if not d_arcade_dbs[db_key]:
            LOGGER.error("There's no Arcade %s JSON data", db_key)
            sys.exit(2)

    print(f'* Checking {d_db_params["name"]} ZIP files cache...')
    chk_zip_cache(d_arcade_dbs['arcade_rom_db'], d_arcade_dbs['cores_db'],
                  s_roms_path, False)

    print(f'* Checking {d_db_params["name"]} MRA files cache...')
    s_baseurl: str = d_db_params['mra_url']
    d_mras: dict[str, Any] = chk_mra_cache(d_arcade_dbs['mra_db'],
                                           d_arcade_dbs['cores_db'],
                                           s_mras_path, False, s_baseurl)

    print(f'* Building {d_db_params["name"]} ARC files...')
    build_arc_files(d_mras, d_arcade_dbs['cores_db'],
                    os.path.join(s_outdir, 'JOTEGO'), s_mras_path, s_roms_path,
                    s_dir)

    return True


def build_autoboot(s_dir: str, s_autoboot: str, s_outdir: str) -> bool:
    """
    Builds file and exdos configuration to autoboot
    :param sdir: BAS files directory
    :param s_autoboot: Name of the BAS file to use
    :param s_outdir: Base directory where the SD files are created
    :return: True if everything is done correctly
    """
    s_autoboot_bin: str = f'AUTOBOOT_{s_autoboot}.BAS'.upper()
    print('Configuring autoboot...')

    chk_or_download_autoboot(s_autoboot_bin, s_dir)
    try:
        shutil.copyfile(os.path.join(s_dir, s_autoboot_bin),
                        os.path.join(s_outdir, 'SYS', 'AUTOBOOT.BAS'))
    except OSError as err:
        LOGGER.error(err)
        return False

    s_config_path: str = os.path.join(s_outdir, 'SYS', 'CONFIG', 'ESXDOS.CFG')
    s_config: str = ''
    with open(s_config_path, 'r', encoding='ascii') as f_handle:
        s_config = f_handle.read()

    s_configured: str = ''
    for s_line in s_config.split('\n'):
        if s_line.lower().startswith('autoboot='):
            s_line = 'AutoBoot=3'
        s_configured += (f'{s_line}\n')

    with open(s_config_path, 'w', encoding='ascii') as f_handle:
        f_handle.write(s_configured)

    return True


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


def build_sd_files(d_files_db: dict[str, Any], l_kinds: list[str],
                   l_types: list[str], b_mist: bool, l_tags: list[str],
                   s_files_path: str, s_out_path: str, s_out_subpath: str,
                   b_taggroups: bool, b_typegroups: bool,
                   b_keep: bool) -> bool:
    """
    Builds SD downloading individual files according to filtering criteria
    :param d_files_db: Database with all the files information
    :param l_kinds: Kind of core files to use (a100t, a35t, etc.)
    :param l_types: Type of core files to use (bit, zx3, etc.)
    :param b_mist: True if mist mode is active
    :param l_tags: Tags of the files to use (computer, arcade, etc.)
    :param s_files_path: Path where the original files are
    :param s_out_path: Path where the files are to be copied
    :param s_out_subpath: Subpath of s_out_path to copy the files into
    :param b_taggroups: Group the files in directories by tag
    :param b_typegroups: Group the files in directories ty type
    :param b_keep: If true, do not delete previously existing files
    :return: Boolean indicating success
    """

    b_ok: bool = True

    if not b_keep:
        s_sdpath: str = os.path.join(s_out_path, 'mist')
        if b_mist and s_out_subpath == 'cores':
            if os.path.isdir(s_sdpath):
                shutil.rmtree(s_sdpath)
        s_sdpath = os.path.join(s_out_path, s_out_subpath)
        if os.path.isdir(s_sdpath):
            shutil.rmtree(s_sdpath)

    d_files: dict[str, Any] = d_files_db['files']
    d_tags: dict[str, Any] = d_files_db.get('tag_dictionary', {})

    if b_mist and s_out_subpath == 'cores' and 'bit' in l_types:
        b_ok = build_zxt_sd_files(d_files, s_files_path, s_out_path, 'mist')
    for s_file in d_files:
        s_name: str = s_file.split('/')[-1]
        s_kind: str = d_files[s_file].get('kind', '')
        s_type: str = d_files[s_file].get('type', '')
        s_sdpath: str = os.path.join(s_out_path, s_out_subpath)
        if b_mist and s_out_subpath == 'cores' and s_type == 'bit':
            s_sdpath = os.path.join(s_out_path, 'mist')

        s_orig: str = ''
        if d_tags:
            if s_kind in l_kinds and s_type in l_types:  # Fully tagged item, copy if tag matches
                if b_typegroups and not (b_mist and s_type == 'bit'):
                    s_sdpath = os.path.join(s_sdpath, d_files[s_file]['type'])
                for i_item in d_files[s_file]['tags']:
                    for j_item in d_tags:
                        if d_tags[j_item] == i_item and j_item in l_tags:
                            if b_taggroups:
                                s_sdpath = os.path.join(s_sdpath, j_item)
                            s_orig = os.path.join(s_files_path, s_name)

            elif not s_kind:  # Partially tagged item?
                for i_item in d_files[s_file]['tags']:
                    for j_item in d_tags:
                        if d_tags[j_item] == i_item and j_item in l_tags:
                            l_subpath: list[str] = d_files[s_file].get(
                                "path", [])
                            s_orig: str = s_files_path
                            if l_subpath:
                                s_orig = os.path.join(s_orig,
                                                      os.path.join(*l_subpath))
                                s_sdpath = os.path.join(
                                    s_sdpath, os.path.join(*l_subpath))
                            s_orig = os.path.join(s_orig, s_name)

        else:  # No tags, always copy
            s_orig_subpath: str = s_files_path
            l_origsubpath: list[str] = d_files[s_file].get('path', [])
            if l_origsubpath:
                s_orig_subpath = os.path.join(s_orig_subpath,
                                              os.path.join(*l_origsubpath))
                s_sdpath = os.path.join(s_sdpath, os.path.join(*l_origsubpath))
            s_orig = os.path.join(s_orig_subpath, s_name)

        if s_orig:
            s_dest: str = os.path.join(s_sdpath, s_name)
            LOGGER.debug('Copy %s to %s...', s_orig, s_dest)
            if not os.path.isdir(s_sdpath):
                pathlib.Path(s_sdpath).mkdir(parents=True, exist_ok=True)
            try:
                shutil.copyfile(s_orig, s_dest)
            except OSError as err:
                LOGGER.error(err)
                b_ok = False

    return b_ok


def build_zxt_sd_files(d_files: dict[str, Any], s_files_path: str,
                       s_out_path: str, s_out_subpath: str) -> bool:
    """
    Tries to build ZXT for SD after downloading individual files
    :param d_files_db: Database with all the files information
    :param s_files_path: Path where the original files are
    :param s_out_path: Path where the files are to be copied
    :param s_out_subpath: Subpath of s_out_path to copy the files into
    """
    b_ok: bool = False
    s_kind = ''

    d_zxt: dict[str, dict[str, str]] = {}
    for s_file in d_files:
        s_name: str = s_file.split('/')[-1]
        s_kind: str = d_files[s_file].get('kind', '')
        if d_files[s_file].get('type', '') == 'bit':
            s_zxtname: str = s_name.replace(s_kind, '').replace('__', '_')
            s_zxtname = s_zxtname.replace('_.', '.')
            if not s_zxtname in d_zxt:
                d_zxt[s_zxtname] = {}
            d_zxt[s_zxtname][s_kind] = s_file

    for s_core, d_bitfiles in d_zxt.items():
        if s_kind and s_kind in d_bitfiles and len(d_bitfiles) == 3:
            arr_bitfiles: list[str] = []
            for z_kind in ['a35t', 'a100t', 'a200t']:
                s_file: str = d_bitfiles[z_kind]
                if s_file:
                    if z_kind in d_bitfiles:
                        del d_files[s_file]
                    s_file = os.path.join(s_files_path, s_file)
                    arr_bitfiles.append(s_file)

            if len(arr_bitfiles) == 3:
                s_name: str = s_core.replace('.bit', '')

                s_sdpath = os.path.join(s_out_path, s_out_subpath)
                if not os.path.isdir(s_sdpath):
                    pathlib.Path(s_sdpath).mkdir(parents=True, exist_ok=True)
                s_sdpath: str = os.path.join(s_sdpath, f'{s_name}.zxt')
                build_zxt_file(arr_bitfiles, s_sdpath)
                b_ok = True

    return b_ok


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


def build_zxt_file(bit_files: list[str], zxt_file: str):
    """
    Join up to three bit files to a ZXT 
    :param bit_files: Path to to three bit files [a35, a100, a200]
    :param zxt_file: New ZXT file to create
    """

    LOGGER.debug('Join %s into %s...', bit_files, zxt_file)

    b_data: bytes = b'MJ\x01\x00'  # ZXT file begings with these magic bytes
    b_filedata: bytes = b''  # Temporary storage for .bit files data

    i_offset: int = 512  # First 512 bytes of ZXT are reserved
    for str_file in bit_files:
        i_size: int = 0
        i_padding: int = 0
        if str_file:
            i_size = os.stat(str_file).st_size
            # Calculate padding to 512 bytes
            i_padding = i_size % 512
            if i_padding:
                i_padding = 512 - i_padding

        b_offset: bytes = int(0).to_bytes(4, 'little')  # Offset binary data
        if i_size:
            b_offset = i_offset.to_bytes(4, 'little')
            # LOGGER.debug(i_offset, b_offset)
            i_offset += i_size + i_padding  # Increase offset with data size

            with open(str_file, 'rb') as in_zxdata:
                b_tempdata: bytes = in_zxdata.read()
                b_filedata += b_tempdata  # Store bit data
                b_filedata += b'\x00' * i_padding  # Pad data to 512 bytes
        b_data += b_offset  # Store offset

    b_data += b'\x00' * 496  # Pad header with zeros up to 512 bytes
    b_data += b_filedata  # Store bit binary data

    with open(zxt_file, 'wb') as out_zxdata:
        out_zxdata.write(b_data)
        LOGGER.debug('%s created OK.', zxt_file)


def build_arc_files(d_mras: dict[str, Any], d_cores_db: dict[str, Any],
                    s_out_path: str, s_mras_path: str, s_roms_path: str,
                    s_cache_path: str):
    """
    Builds ARC and ROM files from MRA and ROM ZIP files
    :param d_mras: Dict with MRA groups info
    :param s_out_path: Base path where the ARC and ROM files are created
    :param s_mras_path: Path for the MRA files cache
    :param s_roms_path: Path for the ROM ZIP files cache
    :param s_cache_path: Path to the main cache (to find the bin)
    :return: Nothing
    """

    if not os.path.isdir(s_out_path):
        pathlib.Path(s_out_path).mkdir(parents=True, exist_ok=True)

    s_mra_bindirpath: str = os.path.join(s_cache_path, 'bin')
    s_mra_binpath: str = chk_or_download_mrabin(s_mra_bindirpath)
    if s_mra_binpath != '':
        for s_mra, l_mra in d_mras.items():
            s_basename_arc: str = ''.join(s_mra.split('arcade'))
            s_subdir_arc: str = ''
            if len(l_mra) > 1:
                s_subdir_arc: str = ''.join(s_basename_arc.split('jt')).upper()

            for s_submra in l_mra:
                s_mra_path: str = os.path.join(s_mras_path, s_submra)
                default_mra: str = d_cores_db[s_basename_arc]['default_mra']
                l_mra_params: list[str] = []

                s_arc_path: str = s_out_path
                if s_subdir_arc == '' or (default_mra != '' and
                                          s_submra.startswith(default_mra)):
                    s_arc_name: str = ''.join(s_mra.split('arcade')) + '.arc'
                    if d_cores_db[s_basename_arc]['default_arc'] != '':
                        s_arc_name = d_cores_db[s_basename_arc][
                            'default_arc'] + '.arc'

                    l_mra_params = [
                        s_mra_binpath, '-A', '-z', s_roms_path, '-O',
                        s_arc_path, '-a',
                        s_arc_name.upper(), s_mra_path
                    ]
                    run_process(l_mra_params, s_submra)

                if s_subdir_arc != '':
                    s_arc_path = os.path.join(s_arc_path, s_subdir_arc)
                    if not os.path.isdir(s_arc_path):
                        pathlib.Path(s_arc_path).mkdir(parents=True,
                                                       exist_ok=True)

                l_mra_params = [
                    s_mra_binpath, '-A', '-z', s_roms_path, '-O', s_arc_path,
                    s_mra_path
                ]
                run_process(l_mra_params, s_submra)


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

    mra_process: CompletedProcess[Any] = run(l_mra_params,
                                             capture_output=True,
                                             check=False,
                                             encoding='utf8')
    if mra_process.stdout != '':
        LOGGER.debug(mra_process.stdout)
    if mra_process.stderr != '':
        LOGGER.error('Problem processing %s: %s', s_item, mra_process.stderr)


if __name__ == "__main__":
    main()
