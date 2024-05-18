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
import argparse
import pathlib
import os
import json
import ssl
from zipfile import ZipFile, is_zipfile
from urllib.parse import urljoin
import socket
import shutil
from builders import (build_zxt_file, build_arc_files)
from checkers import (chk_files_cache, chk_zip_cache, chk_mra_cache,
                      chk_or_download_autoboot)
from utils import chk_or_obtain

__MY_VERSION__ = '1.2.0'

MY_BASEPATH: str = os.path.dirname(sys.argv[0])
MY_DIRPATH: str = os.path.abspath(MY_BASEPATH)

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-5.5s] - %(name)s: %(message)s')
LOGGER = logging.getLogger(__name__)

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
        logging.getLogger('builders').setLevel(logging.DEBUG)
        logging.getLogger('checkers').setLevel(logging.DEBUG)
        logging.getLogger('utils').setLevel(logging.DEBUG)

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


if __name__ == "__main__":
    main()
