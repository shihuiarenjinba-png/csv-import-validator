"""Verify an actual MSIX candidate against the canonical product and registration JSON."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from store.validate_store_config import LOGOS, validate_config  # noqa: E402

NS = {
    "m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
}

EXPECTED_MIN_VERSION = "10.0.17763.0"


def verify_msix(root: Path, msix: Path, version: str | None = None) -> dict:
    root = Path(root).resolve()
    msix = Path(msix).resolve()
    blockers: list[str] = []
    preflight = validate_config(root, version)
    blockers.extend(preflight["blockers"])
    product = json.loads((root / "store" / "product.json").read_text(encoding="utf-8"))
    record = json.loads((root / "store" / "partner_center_registration.json").read_text(encoding="utf-8"))
    identity = record.get("storeIdentity") or {}
    expected_version = preflight.get("version_to_build")
    try:
        if msix.suffix.lower() != ".msix" or not msix.is_file():
            blockers.append("MSIX file does not exist or path is not .msix.")
        else:
            with zipfile.ZipFile(msix, "r") as archive:
                names = archive.namelist()
                if len(names) != len(set(names)):
                    blockers.append("MSIX archive has duplicate entry names.")
                required = {"AppxManifest.xml", f"App/{product.get('exeName', '')}.exe"}
                required.update(f"Assets/{name}" for name in LOGOS)
                missing = sorted(required.difference(names))
                if missing:
                    blockers.append(f"MSIX archive is missing required entries: {missing}")
                if "AppxManifest.xml" not in names:
                    raise ValueError("AppxManifest.xml is missing.")
                manifest = ET.fromstring(archive.read("AppxManifest.xml"))
                identity_node = manifest.find("m:Identity", NS)
                if identity_node is None:
                    blockers.append("Manifest Identity element is missing.")
                else:
                    expected = {
                        "Name": identity.get("packageIdentityName"),
                        "Publisher": identity.get("packageIdentityPublisher"),
                        "ProcessorArchitecture": "x64",
                        "Version": expected_version,
                    }
                    for attr, value in expected.items():
                        if not value or identity_node.get(attr) != value:
                            blockers.append(f"Manifest Identity/{attr} does not match canonical approved data.")
                    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.0", identity_node.get("Version", "")):
                        blockers.append("Manifest revision must be 0.")
                properties = manifest.find("m:Properties", NS)
                display_node = properties.find("m:DisplayName", NS) if properties is not None else None
                publisher_node = properties.find("m:PublisherDisplayName", NS) if properties is not None else None
                expected_display = record.get("displayName")
                if display_node is None or not expected_display or display_node.text != expected_display:
                    blockers.append("Package/Properties/DisplayName does not match canonical data.")
                if publisher_node is None or not identity.get("publisherDisplayName") or publisher_node.text != identity.get("publisherDisplayName"):
                    blockers.append("Package/Properties/PublisherDisplayName does not match canonical data.")
                dependency = manifest.find("m:Dependencies/m:TargetDeviceFamily", NS)
                if dependency is None:
                    blockers.append("Manifest TargetDeviceFamily is missing.")
                else:
                    if dependency.get("Name") != "Windows.Desktop":
                        blockers.append("Manifest TargetDeviceFamily/@Name must be Windows.Desktop.")
                    if dependency.get("MinVersion") != EXPECTED_MIN_VERSION:
                        blockers.append("Manifest TargetDeviceFamily/@MinVersion does not match the approved packaging route.")
                app = manifest.find("m:Applications/m:Application", NS)
                if app is None:
                    blockers.append("Manifest Application element is missing.")
                else:
                    if app.get("Id") != product.get("appId"):
                        blockers.append("Manifest Application/@Id does not match product.json.")
                    expected_exe = f"App\\{product.get('exeName', '')}.exe"
                    if app.get("Executable", "").replace("/", "\\") != expected_exe:
                        blockers.append("Manifest Application/@Executable does not match packaged EXE.")
                    visual = app.find("uap:VisualElements", NS)
                    if visual is None or visual.get("DisplayName") != expected_display:
                        blockers.append("uap:VisualElements/@DisplayName does not match reserved display name.")
                found_languages = sorted(item.get("Language", "") for item in manifest.findall("m:Resources/m:Resource", NS))
                expected_languages = sorted(record.get("manifestResources") or [])
                if found_languages != expected_languages:
                    blockers.append("Manifest Resources do not match approved manifestResources.")
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError, ValueError) as exc:
        blockers.append(f"Cannot inspect MSIX package: {exc}")

    details = None
    if msix.is_file():
        digest = hashlib.sha256()
        with msix.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        details = {
            "path": str(msix),
            "filename": msix.name,
            "size_bytes": msix.stat().st_size,
            "sha256": digest.hexdigest(),
            "signature_status": "QA_UNSIGNED_EXPECTED",
        }
    blockers = list(dict.fromkeys(blockers))
    return {
        "valid": not blockers,
        "product": record.get("displayName"),
        "store_id": identity.get("storeId"),
        "version": expected_version,
        "msix": details,
        "certification_ready": False,
        "sales_release": "HOLD",
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--msix", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--version")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify_msix(args.root, args.msix, args.version)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
