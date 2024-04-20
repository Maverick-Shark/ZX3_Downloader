# ZX3 Downloader

Copyright (c) 2023-2024, kounch

All rights reserved.

---

Select your desired language / Elija idioma:

- Click [this link for English](#english)

- Pulse [este enlace para Castellano](#castellano)

---

## English

### Features

This is a tool that creates most of the file and directory structure of a microSD card for the [ZXTRES family](https://github.com/zxtres/) of FPGA devices.

These are the main features:

- Uses multiple sources to obtain download information
- Downloads ZIP, MRA, BIT, ZX3, etc. files from the sources in the obtained metadata
- Downloads (if needed) [mra tool](https://github.com/kounch/mra-tools-c/tree/master/release) for the current OS (Mac, Windows or Linux)
- Builds the SD structure

### Optional Software Requirements

- Only for the script release **Python (version 3.9 or later)** is needed. Docs, downloads, etc. [here](https://www.python.org/)

### Installation and Use

Copy the binary file `ZX3_Downloader...` to a directory with enough available space (4.5GB, at least, if using the default options), and execute the script telling the kind of FPGA target (`a35t` for ZXTRES, `a100t` for ZXTRES+, `a200t` for ZXTRES++).

For example, for ZXTRES++ on macOS

     ZX3_Downloader -k a200t

On Windows

     ZX3_Downloader.exe -k a200t

Or for the script on Windows (if Python is installed)

    ...python.exe ZX3_Downloader.py -k a200t

This will create the file and directory structure including things like [esxdos](http://www.esxdos.org/index.html), [extra commands](https://github.com/zxtres/dot_commands), [cores](https://github.com/zxtres/cores), etc.

Once the process is finished, if there wer no errors, copy the contents of the `SD` directory to the root of a microSD card.

If something happens that interrupts the download of files, it is recommended to execute the script again, which will try to continue from that last failure.

### Advanced use

The script has the following parameters:

    -v, --version         show program's version number and exit
    -c, --clean_sd        Make a clean build erasing all files at the destination
    -C CACHE_DIR, --cache_dir CACHE_DIR
                          Cache directory name and location
    -O OUT_DIR, --out_dir OUT_DIR
                          Output directory name and location
    -E EXTRA_DIR, --extra_dir EXTRA_DIR
                          Extra content directory name and location
    -K, --keep            Try to keep previous existing files and directories
    -k KINDS, --kinds KINDS
                          List of kinds of fpgas to consider
    -t TYPES, --types TYPES
                          List of types of core files to include (BIT, ZX3)
    -m --mode MODE        Bit core deploy mode to mist directory (mist) or to cores... (legacy)
    -T TAGS, --tags TAGS  List of category content tags to include  (arcade,
                          console, computer, util)
    -g, --group_types     Group core files by file type
    -G, --group_tags      Group core files by tag
    -a AUTOBOOT, --autoboot AUTOBOOT
                          Define autoboot type -directory- (only when grouping by type)
    -n, --no_autoboot     No autoboot install

---

## Castellano

### Características

Esta es una herramienta que crea la mayoría de la estructura de archivos y directorios para una tarjeta microSD para la [familia ZXTRES](https://github.com/zxtres/) de dispositivos FPGA.

Sus características principales son:

- Utiliza múltiples fuentes para obtener información de descarga
- Descarga archivos ZIP, MRA, BIT, ZX3, etc. de las fuentes de los metadatos obtenidos
- Descarga (si fuera necesario) la [herramienta mra](https://github.com/kounch/mra-tools-c/tree/master/release) para el sistema operativo utilizado (Mac, Windows o Linux)
- Construye la estructura de archivos para la SD

### Software opcionalmente necesario

- Para ejecutar el script, es necesario **Python (versión 3.9 o superior)**. Documentación, descarga, etc. [aquí](https://www.python.org/)

### Instalación y uso

Copiar el fichero binario `ZX3_Downloader...` en un directorio con suficiente espacio disponible (al menos, 4,5GB, si se usan las opciones por defecto), y ejecutar el script indicando el tipo de FPGA  (`a35t` para ZXTRES, `a100t` para ZXTRES+, `a200t` para ZXTRES++).

Por ejemplo, en macOS

    ZX3_Downloader -k a200t

En Windows

    ZX3_Downloader.exe -k a200t

o bien para el script en Windows (si Python está instalado)

    ...python.exe ZX3_Downloader.py -k a200t

Esto creará una estructura de ficheros y directorios que incluye cosas como [esxdos](http://www.esxdos.org/index.html), [comandos extra](https://github.com/zxtres/dot_commands), [cores](https://github.com/zxtres/cores), etc.

Una vez el proceso haya finalizado, si no se han producido errores, copiar el contenido del directorio `SD` a la raíz de una tarjeta microSD para utilizarlo.

Si se produjera alguna situación que interrumpa la descarga de ficheros, se recomienda volver a lanzar el script, que continuará a partir de ese último fallo.

### Uso avanzado

El script tiene los siguientes parámetros:

    -v, --version           Mostrar el número de versión del programa y salir
    -c, --clean_sd          Borrar todos los ficheros en el destino y crear una SD limpia
    -C CACHE_DIR, --cache_dir CACHE_DIR
                            Cambiar la ubicación del directorio de la Caché
    -O OUT_DIR, --out_dir OUT_DIR
                            Cambiar el nombre y la ubicación del directorio de salida
    -a, --force_arcade_db
                            Fuerza la descarga de nuevo de la base de datos de Arcade almacenada en caché
    -E EXTRA_DIR, --extra_dir EXTRA_DIR
                            Nombre y ubicación de un directorio con contenido extra
    -K, --keep              Intentar mantener los ficheros anteriores cuando sea posible
    -k KINDS, --kinds KINDS
                            Lista de tipos de FPGAs a considerar
    -t TYPES, --types TYPES
                            Lista de tipos de ficheros de core a incluir (bit, zx3)
    -m --mode MODE          Modo de despliegue de cores en directorio mist (mist) o en cores... (legacy)
    -T TAGS, --tags TAGS    Lista de categorías de contenido a incluir (arcade, console,
                            computer, util)
    -g, --group_types       Agrupar los ficheros de core por tipo
    -G, --group_tags        Agrupar los ficheros de core por tipo de contenido
    -a AUTOBOOT, --autoboot AUTOBOOT
                            Definir el tipo (directorio) de autoarranque (sólo al agrupar por tipo de core)
    -n, --no_autoboot       No configurar autoarranque

---

## License

BSD 2-Clause License

Copyright (c) 2023-2024, kounch
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

- Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

- Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

---

[Update All](https://github.com/theypsilon/Update_All_MiSTer) for [MiSTer](https://github.com/MiSTer-devel/Main_MiSTer/wiki)

Copyright © 2020-2024, [José Manuel Barroso Galindo](https://twitter.com/josembarroso).
Released under the [GPL v3 License](LICENSE).
