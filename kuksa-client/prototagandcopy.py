# /********************************************************************************
# * Copyright (c) 2024 Contributors to the Eclipse Foundation
# *
# * See the NOTICE file(s) distributed with this work for additional
# * information regarding copyright ownership.
# *
# * This program and the accompanying materials are made available under the
# * terms of the Apache License 2.0 which is available at
# * http://www.apache.org/licenses/LICENSE-2.0
# *
# * SPDX-License-Identifier: Apache-2.0
# ********************************************************************************/

import shutil
import os

# this needs to be adapted once the submodules name or structure changes
PROTO_PATH = os.path.abspath("../submodules/kuksa-proto/kuksa/")


def main():
    '''
    This will copy the kuksa proto tree to the current working directory and tag all
    folders as Python packages by creating an __init__.py file in each of them.
    '''
    shutil.copytree(PROTO_PATH, os.path.join(os.getcwd(), "kuksa"), dirs_exist_ok=True)
    for root, dirs, files in os.walk(os.path.join(os.getcwd(), "kuksa")):
        for directory in dirs:
            # Create an __init__.py file in each subdirectory
            init_file = os.path.join(root, directory, "__init__.py")
            with open(init_file, "w") as file:
                file.write("# This file marks the directory as a Python module")
    # The package root itself also needs an __init__.py
    with open(os.path.join(os.getcwd(), "kuksa", "__init__.py"), "w") as file:
        file.write("# This file marks the directory as a Python module")


if __name__ == "__main__":
    main()
