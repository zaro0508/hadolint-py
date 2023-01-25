#!/usr/bin/env python3

import hashlib
import http
import os.path
import platform
import stat
import urllib.request
from distutils.command.build import build as orig_build
from distutils.core import Command

from setuptools import setup
from setuptools.command.install import install as orig_install


HADOLINT_VERSION = "2.11.0"
ARCHIVE_SHA256 = {'darwin-x86_64': ('https://github.com/hadolint/hadolint/releases/download/v2.11.0/hadolint-Darwin-x86_64', '549a0bf32c68e19d9c77dd62db4df8e88340349c29da28133a53bd0e5016f6f4'), 'linux-arm64': ('https://github.com/hadolint/hadolint/releases/download/v2.11.0/hadolint-Linux-arm64', '64ee291c32d1ff4a5d596e3ee1c7f89c733114364dce83f6ab91a21e40a56b79'), 'linux-x86_64': ('https://github.com/hadolint/hadolint/releases/download/v2.11.0/hadolint-Linux-x86_64', 'e1f20d4f8c7d1584271263aad69463aa7b01f4ace91221466de104bcca9245f0'), 'windows-x86_64': ('https://github.com/hadolint/hadolint/releases/download/v2.11.0/hadolint-Windows-x86_64.exe', '37e32da38d68c53b7fd0a8438d0e41e5279f83d177f2295d6672c4d9554d7f04')}
BASE_URL = "https://github.com/hadolint/hadolint/releases/download"
PY_VERSION = "1"


def get_download_url() -> str:
    os, arch = platform.system().lower(), platform.machine().lower()
    if (
        os == "windows"
        or "x86" in arch
        or "amd" in arch
        or "i386" in arch
        or "i686" in arch
    ):
        arch = "x86_64"
    elif "arm" in arch or arch == "aarch64":
        arch = "arm64"

    archive, sha256 = ARCHIVE_SHA256[f"{os}-{arch}"]
    url = f"{BASE_URL}/v{HADOLINT_VERSION}/{archive}"

    url, sha256 = ARCHIVE_SHA256[f"{os}-{arch}"]

    return url, sha256


def download(url: str, sha256: str) -> bytes:
    with urllib.request.urlopen(url) as resp:
        code = resp.getcode()
        if code != http.HTTPStatus.OK:
            raise ValueError(f"HTTP failure. Code: {code}")
        data = resp.read()

    checksum = hashlib.sha256(data).hexdigest()
    if checksum != sha256:
        raise ValueError(f"sha256 mismatch, expected {sha256}, got {checksum}")

    return data


def save_executable(data: bytes, base_dir: str):
    exe = "hadolint" if platform.system() != "Windows" else "hadolint.exe"
    output_path = os.path.join(base_dir, exe)
    os.makedirs(base_dir)

    with open(output_path, "wb") as fp:
        fp.write(data)

    # Mark as executable.
    # https://stackoverflow.com/a/14105527
    mode = os.stat(output_path).st_mode
    mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    os.chmod(output_path, mode)


class build(orig_build):
    sub_commands = orig_build.sub_commands + [("fetch_binaries", None)]


class install(orig_install):
    sub_commands = orig_install.sub_commands + [("install_hadolint", None)]


class fetch_binaries(Command):
    build_temp = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.set_undefined_options("build", ("build_temp", "build_temp"))

    def run(self):
        # save binary to self.build_temp
        url, sha = get_download_url()
        data = download(url, sha)
        save_executable(data, self.build_temp)


class install_hadolint(Command):
    description = "install the hadolint executable"
    outfiles = ()
    build_dir = install_dir = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        # this initializes attributes based on other commands' attributes
        self.set_undefined_options("build", ("build_temp", "build_dir"))
        self.set_undefined_options(
            "install",
            ("install_scripts", "install_dir"),
        )

    def run(self):
        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)

    def get_outputs(self):
        return self.outfiles


command_overrides = {
    "install": install,
    "install_hadolint": install_hadolint,
    "build": build,
    "fetch_binaries": fetch_binaries,
}


try:
    from wheel.bdist_wheel import bdist_wheel as orig_bdist_wheel
except ImportError:
    pass
else:

    class bdist_wheel(orig_bdist_wheel):
        def finalize_options(self):
            orig_bdist_wheel.finalize_options(self)
            # Mark us as not a pure python package
            self.root_is_pure = False

        def get_tag(self):
            _, _, plat = orig_bdist_wheel.get_tag(self)
            # We don't contain any python source, nor any python extensions
            return "py2.py3", "none", plat

    command_overrides["bdist_wheel"] = bdist_wheel

setup(version=f"{HADOLINT_VERSION}.{PY_VERSION}", cmdclass=command_overrides)
