#!/usr/bin/env python3
"""Build OSCAL Component Definition directly from downloaded raw Privateer (pvtr) data."""

import argparse
import datetime
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml
from trestle.oscal import OSCAL_VERSION
from trestle.oscal.common import Metadata, Property
from trestle.oscal.component import (
    ComponentDefinition,
    ControlImplementation,
    DefinedComponent,
    ImplementedRequirement,
)

NAMESPACE_DNS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
CD_NAMESPACE = "https://oscal-compass/compliance-trestle/schemas/oscal/cd"


def make_uuid(name: str) -> str:
    """Generate a deterministic UUIDv5 conforming to standard UUID format."""
    return str(uuid.uuid5(NAMESPACE_DNS, f"cncf-checks:{name}"))


def clean_text(text: str) -> str:
    """Normalize text into a single-line string for OSCAL property values."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def parse_download_dir(download_dir: Path) -> Dict[str, Any]:
    """Parse all downloaded YAML/JSON files from Privateer repository."""
    capabilities = []
    controls = []
    checks = []

    files = sorted(
        list(download_dir.glob("*.yaml"))
        + list(download_dir.glob("*.yml"))
        + list(download_dir.glob("*.json"))
    )
    if not files:
        print(f"Warning: No files found in {download_dir}", file=sys.stderr)
        return {"capabilities": capabilities, "controls": controls, "checks": checks}

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f) if file_path.suffix == ".json" else yaml.safe_load(f)

        if not data:
            continue

        if isinstance(data, dict):
            if "capabilities" in data:
                for cap in data["capabilities"]:
                    cap["source_file"] = file_path.name
                    capabilities.append(cap)
            if "controls" in data:
                for ctrl in data["controls"]:
                    ctrl["source_file"] = file_path.name
                    controls.append(ctrl)
            if "checks" in data:
                for chk in data["checks"]:
                    checks.append(chk)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "capabilities" in item:
                        capabilities.extend(item["capabilities"])
                    elif "controls" in item:
                        controls.extend(item["controls"])
                    elif "id" in item:
                        checks.append(item)

    return {"capabilities": capabilities, "controls": controls, "checks": checks}


def build_component_definition(download_dir: Path) -> ComponentDefinition:
    """Build the OSCAL Component Definition using Trestle native models."""
    parsed = parse_download_dir(download_dir)
    capabilities = parsed["capabilities"]
    controls = parsed["controls"]
    checks = parsed["checks"]

    now_dt = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    validation_props: List[Property] = []
    implemented_requirements: List[ImplementedRequirement] = []

    item_idx = 0

    # Process Privateer capabilities
    for cap in capabilities:
        check_set_tag = f"check_set_{item_idx:02d}"
        rule_set_tag = f"rule_set_{item_idx:02d}"
        cap_id = clean_text(cap.get("id", f"cap_{item_idx}"))
        cap_title = clean_text(cap.get("title", cap_id))
        cap_desc = clean_text(cap.get("description", cap_title))
        rule_id = cap_id.lower().replace(".", "_")

        validation_props.extend([
            Property(name="Rule_Id", ns=CD_NAMESPACE, value=rule_id, remarks=check_set_tag),
            Property(name="Check_Id", ns=CD_NAMESPACE, value=cap_id, remarks=check_set_tag),
            Property(name="Check_Description", ns=CD_NAMESPACE, value=cap_desc, remarks=check_set_tag),
            Property(name="Target_Component", ns=CD_NAMESPACE, value="Privateer CLI", remarks=check_set_tag),
        ])

        ctrl_id = clean_text(cap.get("group", "general")).lower()
        implemented_requirements.append(
            ImplementedRequirement(
                uuid=make_uuid(f"implemented-req:{cap_id}"),
                control_id=ctrl_id,
                description=f"{cap_title}: {cap_desc}",
                props=[
                    Property(name="Rule_Id", ns=CD_NAMESPACE, value=rule_id, remarks=rule_set_tag),
                    Property(name="Rule_Description", ns=CD_NAMESPACE, value=cap_title, remarks=rule_set_tag),
                    Property(name="Capability_Group", ns=CD_NAMESPACE, value=clean_text(cap.get("group", "general")), remarks=rule_set_tag),
                ],
            )
        )
        item_idx += 1

    # Process security controls if present
    for ctrl in controls:
        ctrl_id = clean_text(ctrl.get("id", "")).lower()
        ctrl_title = clean_text(ctrl.get("title", ctrl_id))
        ctrl_desc = clean_text(ctrl.get("description", ctrl_title))
        rule_id = f"rule_{ctrl_id.replace('-', '_')}"
        check_set_tag = f"check_set_{item_idx:02d}"
        rule_set_tag = f"rule_set_{item_idx:02d}"

        validation_props.extend([
            Property(name="Rule_Id", ns=CD_NAMESPACE, value=rule_id, remarks=check_set_tag),
            Property(name="Check_Id", ns=CD_NAMESPACE, value=f"check_{ctrl_id}", remarks=check_set_tag),
            Property(name="Check_Description", ns=CD_NAMESPACE, value=f"Validates {ctrl_title}", remarks=check_set_tag),
            Property(name="Target_Component", ns=CD_NAMESPACE, value="Cloud-Native Platform", remarks=check_set_tag),
        ])

        implemented_requirements.append(
            ImplementedRequirement(
                uuid=make_uuid(f"implemented-req:{ctrl_id}"),
                control_id=ctrl_id,
                description=f"{ctrl_title}: {ctrl_desc}",
                props=[
                    Property(name="Rule_Id", ns=CD_NAMESPACE, value=rule_id, remarks=rule_set_tag),
                    Property(name="Rule_Description", ns=CD_NAMESPACE, value=ctrl_title, remarks=rule_set_tag),
                ],
            )
        )
        item_idx += 1

    # Process explicit check manifests if present
    for chk in checks:
        chk_id = clean_text(chk.get("id", f"chk_{item_idx}"))
        chk_name = clean_text(chk.get("name", chk_id))
        chk_desc = clean_text(chk.get("description", chk_name))
        rule_id = clean_text(chk.get("rule_id", chk_id.replace("pvp_", "")))
        target_comp = clean_text(chk.get("target_component", "Cloud-Native Platform"))
        check_set_tag = f"check_set_{item_idx:02d}"

        validation_props.extend([
            Property(name="Rule_Id", ns=CD_NAMESPACE, value=rule_id, remarks=check_set_tag),
            Property(name="Check_Id", ns=CD_NAMESPACE, value=chk_id, remarks=check_set_tag),
            Property(name="Check_Description", ns=CD_NAMESPACE, value=chk_desc, remarks=check_set_tag),
            Property(name="Target_Component", ns=CD_NAMESPACE, value=target_comp, remarks=check_set_tag),
        ])
        item_idx += 1

    if not implemented_requirements:
        implemented_requirements.append(
            ImplementedRequirement(
                uuid=make_uuid("implemented-req:default"),
                control_id="cm-6",
                description="Default configuration baseline enforcement",
                props=[
                    Property(name="Rule_Id", ns=CD_NAMESPACE, value="default_baseline", remarks="rule_set_00"),
                    Property(name="Rule_Description", ns=CD_NAMESPACE, value="Default baseline", remarks="rule_set_00"),
                ],
            )
        )

    # Assemble Software Component
    software_comp = DefinedComponent(
        uuid=make_uuid("comp:cloud-native-platform"),
        type="software",
        title="Cloud-Native Platform",
        description="Cloud-Native Platform and Infrastructure Runtime",
        purpose="Platform execution runtime and security controls",
        control_implementations=[
            ControlImplementation(
                uuid=make_uuid("control-impl:cncf-controls"),
                source="https://github.com/oscal-compass-lab/cncf-controls/catalogs/cncf-controls/catalog.json",
                description="Control implementations evaluated by Privateer (pvtr)",
                implemented_requirements=implemented_requirements,
            )
        ],
    )

    # Assemble Validation Component
    validation_comp = DefinedComponent(
        uuid=make_uuid("comp:privateer"),
        type="validation",
        title="privateer",
        description="Privateer (pvtr) validation test framework",
        props=validation_props,
    )

    # Top-level Component Definition
    cd = ComponentDefinition(
        uuid=make_uuid("cd:privateer"),
        metadata=Metadata(
            title="Component Definition for Privateer (pvtr) Validation",
            last_modified=now_dt,
            version="V1.0",
            oscal_version=OSCAL_VERSION,
        ),
        components=[software_comp, validation_comp],
    )
    return cd


def main() -> None:
    parser = argparse.ArgumentParser(description="Build OSCAL Component Definition from raw Privateer (pvtr) data")
    parser.add_argument(
        "--download-dir",
        "-d",
        type=Path,
        default=Path("download"),
        help="Directory containing downloaded raw Privateer check files (default: download)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("trestle.ws/component-definitions/privateer/component-definition.json"),
        help="Output path for component-definition.json",
    )
    args = parser.parse_args()

    if not args.download_dir.exists():
        print(f"Error: Download directory not found: {args.download_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Building component definition from {args.download_dir} ...")
    cd = build_component_definition(args.download_dir)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cd.oscal_write(args.output)
    print(f"✓ Component definition written to {args.output} (OSCAL version {OSCAL_VERSION})")


if __name__ == "__main__":
    main()
