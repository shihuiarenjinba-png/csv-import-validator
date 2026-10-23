"""Fail-closed MSIX candidate readiness checks; no Partner Center API access."""
from __future__ import annotations
import argparse
import json
import re
import struct
from pathlib import Path

EXPECTED_REPOSITORY = "csv-import-validator"
CONFIRMED_STATES = {"EXISTING_CONFIRMED", "RESERVED_CONFIRMED", "SUBMISSION_DRAFT_CONFIRMED"}
IDENTITY_FIELDS = ("packageIdentityName", "packageIdentityPublisher", "publisherDisplayName", "packageFamilyName")
LOGOS = {
    "StoreLogo.png": (50, 50),
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Wide310x150Logo.png": (310, 150),
}
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+\.0$")
STORE_ID_RE = re.compile(r"^[A-Z0-9]{12}$")
LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2}|-[0-9]{3})?$")


def _read_json(path: Path, blockers: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        blockers.append(f"Cannot read valid JSON at {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        blockers.append(f"Expected a JSON object: {path}")
        return {}
    return value


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">II", header[16:24])
    except (OSError, struct.error):
        return None


def validate_config(root: Path, version: str | None = None) -> dict:
    """Return a deterministic report. Unknown official data is a blocker, not a guess."""
    root = Path(root).resolve()
    blockers: list[str] = []
    warnings: list[str] = []
    store = root / "store"
    product = _read_json(store / "product.json", blockers)
    record = _read_json(store / "partner_center_registration.json", blockers)

    if record.get("repository") != EXPECTED_REPOSITORY:
        blockers.append("Registration repository must identify csv-import-validator.")
    if product.get("displayName") != record.get("displayName"):
        blockers.append("Product displayName and registration displayName must match exactly.")
    if not record.get("displayName"):
        blockers.append("Official Store displayName is missing.")
    if record.get("partnerCenterState") not in CONFIRMED_STATES:
        blockers.append("Partner Center product state is not confirmed.")
    if record.get("certificationSubmission") != "NOT_AUTHORIZED":
        blockers.append("Certification must remain NOT_AUTHORIZED during candidate preparation.")
    if record.get("salesRelease") != "HOLD":
        blockers.append("salesRelease must remain HOLD during candidate preparation.")

    identity = record.get("storeIdentity")
    if not isinstance(identity, dict):
        identity = {}
        blockers.append("storeIdentity must be a JSON object.")
    store_id = identity.get("storeId")
    if not isinstance(store_id, str) or not STORE_ID_RE.fullmatch(store_id):
        blockers.append("A 12-character Store ID is required.")
    if record.get("storeIdVerificationStatus") != "USER_CONFIRMED_NOT_LIVE_VERIFIED":
        blockers.append("Store ID confirmation provenance is not recorded.")
    for field in IDENTITY_FIELDS:
        value = identity.get(field)
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"Official Partner Center identity field is missing: {field}.")
        elif re.search(r"(?i)(example|placeholder|testidentity|yourname)", value):
            blockers.append(f"Sample/placeholder identity is not allowed: {field}.")

    approved_version = record.get("approvedStoreVersion")
    version_to_build = version if version and version.strip() else approved_version
    if not isinstance(approved_version, str) or not VERSION_RE.fullmatch(approved_version):
        blockers.append("approvedStoreVersion is missing or not an approved four-part version ending in .0.")
    if version and version.strip() and version != approved_version:
        blockers.append("Requested version does not exactly match approvedStoreVersion.")
    if isinstance(version_to_build, str) and version_to_build:
        if not VERSION_RE.fullmatch(version_to_build):
            blockers.append("MSIX version must have four numeric components and revision 0.")
        else:
            parts = [int(part) for part in version_to_build.split(".")]
            if parts[0] < 1 or any(part > 65535 for part in parts):
                blockers.append("MSIX version components are outside the permitted range.")

    languages = record.get("manifestResources")
    if not isinstance(languages, list) or not languages:
        blockers.append("manifestResources must contain explicitly approved package languages.")
    elif any(not isinstance(lang, str) or not LANGUAGE_RE.fullmatch(lang) for lang in languages):
        blockers.append("manifestResources contains an invalid language tag.")
    elif len(languages) != len(set(languages)):
        blockers.append("manifestResources contains duplicate language tags.")

    entrypoint = product.get("entryPoint")
    if not isinstance(entrypoint, str) or not entrypoint.endswith(".py") or not (root / entrypoint).is_file():
        blockers.append("Configured Python entry point is missing.")
    exe_name = product.get("exeName")
    if not isinstance(exe_name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,50}", exe_name):
        blockers.append("Configured EXE name is invalid.")
    app_id = product.get("appId")
    if not isinstance(app_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,48}", app_id):
        blockers.append("Configured application ID is invalid.")

    approval_path = store / "assets" / "approval.json"
    approval = _read_json(approval_path, blockers) if approval_path.exists() else {}
    if not approval:
        blockers.append("Owner-approved artwork record store/assets/approval.json is missing.")
    else:
        if approval.get("status") != "OWNER_APPROVED":
            blockers.append("Artwork approval status is not OWNER_APPROVED.")
        if approval.get("product_key") != "data-contract-auditor":
            blockers.append("Artwork approval record belongs to a different product.")
        if not approval.get("approval_ref") or not approval.get("approved_by"):
            blockers.append("Artwork approval reference and approver are required.")
    for filename, expected in LOGOS.items():
        path = store / "assets" / filename
        if not path.is_file():
            blockers.append(f"Required approved logo is missing: store/assets/{filename}.")
        elif _png_dimensions(path) != expected:
            blockers.append(f"Logo {filename} dimensions do not match {expected}.")

    if product.get("commercialLicense") != "CERTIFIED":
        warnings.append("Commercial license evidence is not certified; sales release remains HOLD.")
    if product.get("storeStatus") == "HOLD_OFFICIAL_PARTNER_IDENTITY_REQUIRED":
        warnings.append("Product profile continues to record an official-identity HOLD.")

    blockers = list(dict.fromkeys(blockers))
    return {
        "product": record.get("displayName") or product.get("displayName"),
        "repository": record.get("repository"),
        "store_id": store_id,
        "version_to_build": version_to_build if isinstance(version_to_build, str) else None,
        "ready": not blockers,
        "certification_ready": False,
        "sales_release": "HOLD",
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--version")
    parser.add_argument("--json", action="store_true", help="Emit the readiness report as JSON.")
    args = parser.parse_args()
    report = validate_config(args.root, args.version)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"MSIX_CANDIDATE_READY={str(report['ready']).lower()}")
        for item in report["blockers"]:
            print(f"BLOCKED: {item}")
        for item in report["warnings"]:
            print(f"WARNING: {item}")
    # A HOLD is a valid preflight result; the build script refuses to proceed.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
