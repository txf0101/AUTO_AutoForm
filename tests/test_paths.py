from pathlib import Path

import autoform_agent.paths as paths
from autoform_agent.paths import AutoFormInstallation, discover_installations


def test_installation_path_overrides(monkeypatch, tmp_path: Path) -> None:
    install_root = tmp_path / "install"
    program_data = tmp_path / "program-data" / "R14F"
    monkeypatch.setenv("AUTOFORM_VERSION_DIR", "R14F")
    monkeypatch.setenv("AUTOFORM_PROGRAM_DATA_DIR", str(program_data))
    monkeypatch.setenv("AUTOFORM_MATERIALS_DIR", str(tmp_path / "materials"))
    install = AutoFormInstallation("AutoForm Forming R14", "14.0", install_root)

    assert install.version_dir_name == "R14F"
    assert install.autoform_program_data == program_data
    assert install.materials_dir == tmp_path / "materials"
    assert install.test_dir == program_data / "test"


def test_discover_installations_includes_explicit_install(monkeypatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit" / "R14F"
    monkeypatch.setenv("AUTOFORM_INSTALL_DIR", str(explicit))
    monkeypatch.setattr(paths, "_discover_from_registry", lambda: [])
    monkeypatch.setattr(paths, "_fallback_installations", lambda: [])

    installs = discover_installations()

    assert installs[0].install_location == explicit
    assert "AUTOFORM_INSTALL_DIR" in installs[0].display_name
