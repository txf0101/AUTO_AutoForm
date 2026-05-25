"""AutoForm installation discovery and canonical path calculation.

This module is the portability boundary for the whole project.  Other modules
should ask this module for AutoForm locations instead of hard-coding
`Program Files`, `ProgramData`, or version-specific directories.  Keeping this
logic centralized makes future multi-version and non-standard installation
support easier to maintain.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class AutoFormInstallation:
    """Resolved paths and registry metadata for one AutoForm Forming install.

    The object stores only facts that identify the installation.  Derived
    directories such as `materials_dir` or `scripts_dir` are computed through
    properties so that future overrides can be added in one place.
    """

    display_name: str
    version: str | None
    install_location: Path
    install_date: str | None = None
    publisher: str | None = None

    @property
    def version_dir_name(self) -> str:
        """Return the folder name used below `C:\\ProgramData\\AutoForm\\AFplus`.

        AutoForm R13 installs into a directory such as `R13F`; the same token is
        used in ProgramData.  This assumption is based on the current local
        installation evidence and is the first place to revisit for other
        AutoForm product layouts.
        """
        return self.install_location.name

    @property
    def bin_dir(self) -> Path:
        """Return the directory that contains AutoForm executables."""
        return self.install_location / "bin"

    @property
    def package_info_file(self) -> Path:
        """Return the optional installer metadata file shipped by AutoForm."""
        return self.install_location / "package_info_lite.json"

    @property
    def forming_ui(self) -> Path:
        """Return the GUI executable used to start AutoForm Forming."""
        return self.bin_dir / "AFFormingUI.exe"

    @property
    def splash(self) -> Path:
        """Return the splash launcher used by Start Menu shortcuts."""
        return self.bin_dir / "AFSplash.exe"

    @property
    def forming_job(self) -> Path:
        """Return the batch job executable used by command-line workflows."""
        return self.bin_dir / "AFFormingJob.exe"

    @property
    def forming_job_cmd(self) -> Path:
        """Return the versioned command wrapper observed in the R13 install."""
        return self.bin_dir / "AFFormingJob_R13.cmd"

    @property
    def autoform_program_data(self) -> Path:
        """Return the ProgramData root for this AutoForm version directory."""
        # AutoForm keeps mutable product data under ProgramData, while executables
        # live under the installation directory in Program Files.
        program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        return program_data / "AutoForm" / "AFplus" / self.version_dir_name

    @property
    def materials_dir(self) -> Path:
        """Return the mutable material library root used by AutoForm."""
        return self.autoform_program_data / "materials"

    @property
    def scripts_dir(self) -> Path:
        """Return the QuickLink and automation script directory."""
        return self.autoform_program_data / "scripts"

    @property
    def test_dir(self) -> Path:
        """Return the official sample project directory under ProgramData."""
        return self.autoform_program_data / "test"

    @property
    def quicklink_templates_dir(self) -> Path:
        """Return the QuickLink template and standard definition directory."""
        return self.autoform_program_data / "templates" / "quicklink"

    @property
    def system_config_file(self) -> Path:
        """Return the queue, remote computing and logging configuration file."""
        return self.autoform_program_data / "systemConfigFile.xml"

    @property
    def help_links_file(self) -> Path:
        """Return the help topic mapping file shipped with the installation."""
        return self.install_location / "help" / "helpLinks.cfg"

    def package_info(self) -> dict:
        """Read installer package metadata if the file is present and valid.

        Missing or malformed metadata is treated as an empty dictionary because
        installation discovery should remain usable even when optional installer
        evidence is unavailable.
        """
        if not self.package_info_file.exists():
            return {}
        try:
            return json.loads(self.package_info_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def as_dict(self) -> dict:
        """Return a JSON-ready installation snapshot for CLI and MCP clients."""
        package = self.package_info()
        return {
            "display_name": self.display_name,
            "version": self.version,
            "install_date": self.install_date,
            "publisher": self.publisher,
            "install_location": str(self.install_location),
            "bin_dir": str(self.bin_dir),
            "forming_ui": str(self.forming_ui),
            "splash": str(self.splash),
            "forming_job": str(self.forming_job),
            "forming_job_cmd": str(self.forming_job_cmd),
            "program_data": str(self.autoform_program_data),
            "materials_dir": str(self.materials_dir),
            "scripts_dir": str(self.scripts_dir),
            "test_dir": str(self.test_dir),
            "quicklink_templates_dir": str(self.quicklink_templates_dir),
            "system_config_file": str(self.system_config_file),
            "help_links_file": str(self.help_links_file),
            "package_info": package,
            "exists": {
                "install_location": self.install_location.exists(),
                "forming_ui": self.forming_ui.exists(),
                "splash": self.splash.exists(),
                "forming_job": self.forming_job.exists(),
                "materials_dir": self.materials_dir.exists(),
                "scripts_dir": self.scripts_dir.exists(),
                "system_config_file": self.system_config_file.exists(),
                "help_links_file": self.help_links_file.exists(),
            },
        }


def discover_installations() -> list[AutoFormInstallation]:
    """Find AutoForm through Windows uninstall metadata, then known fallbacks."""

    installs = list(_discover_from_registry())
    installs.extend(_fallback_installations())
    return _dedupe_installations(installs)


def get_default_installation() -> AutoFormInstallation:
    """Return the best available AutoForm installation for single-install flows.

    Current behavior prefers records whose install directory exists.  When
    multi-version support is added, this function should become the policy
    point for version selection.
    """
    installs = discover_installations()
    if not installs:
        raise FileNotFoundError("No AutoForm Forming installation was found.")
    return sorted(installs, key=lambda item: item.install_location.exists(), reverse=True)[0]


def _discover_from_registry() -> Iterable[AutoFormInstallation]:
    """Read Windows uninstall registry keys for AutoForm Forming installs."""
    if os.name != "nt":
        return []

    try:
        import winreg
    except ImportError:
        return []

    roots = [
        # 64-bit and 32-bit uninstall registries are both cheap to inspect and
        # keep this function tolerant of installer differences.
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    ]

    found: list[AutoFormInstallation] = []
    for root, subkey in roots:
        try:
            with winreg.OpenKey(root, subkey) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        child_name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, child_name) as child:
                            display_name = _read_reg_value(winreg, child, "DisplayName")
                            if not display_name or "AutoForm Forming" not in display_name:
                                continue
                            install_location = _read_reg_value(winreg, child, "InstallLocation")
                            if not install_location:
                                continue
                            found.append(
                                AutoFormInstallation(
                                    display_name=display_name,
                                    version=_read_reg_value(winreg, child, "DisplayVersion"),
                                    install_location=Path(install_location),
                                    install_date=_read_reg_value(winreg, child, "InstallDate"),
                                    publisher=_read_reg_value(winreg, child, "Publisher"),
                                )
                            )
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _read_reg_value(winreg_module, key, name: str) -> str | None:
    """Read one registry value and normalize missing values to `None`."""
    try:
        value, _ = winreg_module.QueryValueEx(key, name)
    except OSError:
        return None
    return str(value) if value is not None else None


def _fallback_installations() -> list[AutoFormInstallation]:
    """Use conservative defaults for machines where registry reads are blocked."""

    candidates = [
        Path(r"D:\Program Files\AutoForm\AFplus\R13F"),
        Path(r"C:\Program Files\AutoForm\AFplus\R13F"),
        Path(r"C:\Program Files (x86)\AutoForm\AFplus\R13F"),
    ]
    return [
        AutoFormInstallation(
            display_name="AutoForm Forming R13",
            version=None,
            install_location=path,
        )
        for path in candidates
        if path.exists()
    ]


def _dedupe_installations(installs: Iterable[AutoFormInstallation]) -> list[AutoFormInstallation]:
    """Merge registry and fallback discoveries by normalized install path."""
    deduped: dict[str, AutoFormInstallation] = {}
    for install in installs:
        key = str(install.install_location).casefold().rstrip("\\/")
        existing = deduped.get(key)
        # Prefer registry records with a concrete version over fallback guesses.
        if existing is None or (existing.version is None and install.version is not None):
            deduped[key] = install
    return list(deduped.values())
