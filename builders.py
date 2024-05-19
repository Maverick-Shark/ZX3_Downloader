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
import logging
from utils import run_process
from checkers import chk_or_download_mrabin

LOGGER = logging.getLogger(__name__)


def build_zxt_file(bit_files: list[str], zxt_file: str) -> bool:
    """
    Join up to three bit files to a ZXT 
    :param bit_files: Path to to three bit files [a35, a100, a200]
    :param zxt_file: New ZXT file to create
    """

    LOGGER.debug('Join %s into %s...', bit_files, zxt_file)

    b_ok = False
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
            # LOGGER.debug('%s: %i (%s)', str_file, i_offset, b_offset.hex())
            i_offset += i_size + i_padding  # Increase offset with data size

            with open(str_file, 'rb') as in_zxdata:
                b_tempdata: bytes = in_zxdata.read()
                b_tempdata += b'\xff' * i_padding  # Pad data to 512 bytes
                b_filedata += b_tempdata  # Store bit data

        b_data += b_offset  # Store offset

    b_data += b'\x00' * 496  # Pad header with zeros up to 512 bytes
    b_data += b_filedata  # Store bit binary data

    with open(zxt_file, 'wb') as out_zxdata:
        out_zxdata.write(b_data)
        b_ok = True
        LOGGER.debug('%s created OK.', zxt_file)

    return b_ok


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
