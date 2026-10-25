"""Detailed, machine-readable metadata and archive-range diagnostics."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .archive import ArchiveReader
from .common import __version__
from .paths import OutputManager


def _node(element: ET.Element) -> Dict[str, Any]:
    """Serialize raw XML text and every descendant without interpreting unknown fields."""
    raw_text = element.text
    normalized = raw_text.strip() if raw_text is not None else ""
    return {
        "tag": element.tag,
        "attributes": dict(element.attrib),
        "text": raw_text,
        "text_normalized": normalized or None,
        "tail": element.tail,
        "children": [_node(child) for child in list(element)],
    }


def _range_details(
    attributes: Dict[str, str],
    total_size: int,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    raw_offset = attributes.get("StartOffset")
    raw_size = attributes.get("DataSize")
    details: Dict[str, Any] = {
        "start_offset_raw": raw_offset,
        "data_size_raw": raw_size,
        "start_offset": None,
        "data_size": None,
    }

    if raw_offset is None or raw_size is None:
        details["range_status"] = "missing_numeric_field"
        return details, {
            "code": details["range_status"],
            "start_offset_raw": raw_offset,
            "data_size_raw": raw_size,
            "message": "StartOffset or DataSize is missing.",
        }

    try:
        offset = int(raw_offset)
        size = int(raw_size)
    except (TypeError, ValueError):
        details["range_status"] = "unparsed_numeric_field"
        return details, {
            "code": details["range_status"],
            "start_offset_raw": raw_offset,
            "data_size_raw": raw_size,
            "message": "StartOffset or DataSize is not an integer.",
        }

    details["start_offset"] = offset
    details["data_size"] = size
    if offset < 0 or size < 0 or offset > total_size or size > total_size - offset:
        details["range_status"] = "invalid_or_out_of_bounds"
        problem = {
            "code": details["range_status"],
            "start_offset_raw": raw_offset,
            "data_size_raw": raw_size,
            "message": "The parsed range is negative or outside the archive bounds.",
        }
    else:
        details["range_status"] = "valid"
        problem = None
    return details, problem


def build_metadata_report(
    *,
    root: Optional[ET.Element],
    common_header: Optional[ET.Element],
    archive_path: Path,
    archive: ArchiveReader,
    header_format: Optional[str],
    extract_files_enabled: bool,
    try_path_reconstruct: bool,
    resolve_cg_path: Callable[[str], str],
) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    payload_ranges: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []

    if root is not None:
        for item_index, item in enumerate(root.findall("BackupItem")):
            category = item.get("Category", "UNKNOWN")
            attributes = dict(item.attrib)
            if category == "APPLICATION" and item.findall("APPLICATION"):
                payload_nodes = item.findall("APPLICATION")
                payload_kind = "application"
            else:
                payload_nodes = [item]
                payload_kind = "catalog_item"

            payload_indices = []
            for payload_index, payload_node in enumerate(payload_nodes):
                payload_attributes = dict(payload_node.attrib)
                range_details, range_problem = _range_details(
                    payload_attributes, archive.total_size
                )
                payload = {
                    "item_index": item_index,
                    "payload_index": payload_index,
                    "kind": payload_kind,
                    "category": category,
                    "name": (
                        payload_attributes.get("FileName")
                        or payload_attributes.get("Name")
                        or attributes.get("FileName")
                        or category
                    ),
                    "attributes": payload_attributes,
                    "uninterpreted_attributes": {
                        key: value
                        for key, value in payload_attributes.items()
                        if key not in {
                            "Category", "FileName", "Name", "StartOffset", "DataSize"
                        }
                    },
                    **range_details,
                    "xml": _node(payload_node),
                }
                payload_ranges.append(payload)
                payload_indices.append(len(payload_ranges) - 1)
                if range_problem is not None:
                    diagnostics.append(
                        {
                            **range_problem,
                            "item_index": item_index,
                            "payload_index": payload_index,
                            "category": category,
                        }
                    )

            if "_CG_" in category:
                if not try_path_reconstruct:
                    resolved = category
                    resolution_status = "reconstruction_disabled"
                else:
                    resolved = resolve_cg_path(category)
                    resolution_status = "resolved" if resolved != category else "unresolved"
                if resolution_status == "unresolved":
                    diagnostics.append(
                        {
                            "code": "unresolved_cg_path",
                            "item_index": item_index,
                            "category": category,
                            "message": (
                                "The category contains a CG reference that could "
                                "not be reconstructed."
                            ),
                        }
                    )
                path_input = category
            else:
                path_input = attributes.get("FileName") or category
                resolved = path_input
                resolution_status = "not_applicable"

            entries.append(
                {
                    "index": item_index,
                    "category": category,
                    "attributes": attributes,
                    "uninterpreted_attributes": {
                        key: value
                        for key, value in attributes.items()
                        if key not in {"Category", "FileName", "StartOffset", "DataSize"}
                    },
                    "payload_range_indices": payload_indices,
                    "path_resolution": {
                        "input": path_input,
                        "resolved": resolved,
                        "status": resolution_status,
                    },
                    "xml": _node(item),
                }
            )

    segments = []
    previous_boundary = 0
    for index, path in enumerate(archive.part_paths):
        boundary = archive.part_boundaries[index]
        segments.append(
            {"name": path.name, "size_bytes": boundary - previous_boundary}
        )
        previous_boundary = boundary

    return {
        "report_schema_version": 2,
        "tool": {"name": "lbf-extractor", "version": __version__},
        "archive": {
            "input_name": archive_path.name,
            "total_size_bytes": archive.total_size,
            "segments": segments,
            "header_format": header_format,
        },
        "analysis": {
            "catalog_item_count": len(entries),
            "payload_range_count": len(payload_ranges),
            "diagnostic_count": len(diagnostics),
            "extract_files_enabled": extract_files_enabled,
            "range_status_note": (
                "A valid range is only numerically within archive bounds; "
                "it is not proof that the format interpretation is correct."
            ),
        },
        "common_metadata": _node(common_header) if common_header is not None else None,
        "catalog_items": entries,
        "payload_ranges": payload_ranges,
        "diagnostics": diagnostics,
        "full_header_tree": _node(root) if root is not None else None,
        "sharing_guidance": (
            "This report may contain personal identifiers, paths, contacts, "
            "and message metadata. Redact sensitive data before sharing."
        ),
    }


def write_metadata_report(
    output: OutputManager,
    *,
    root: Optional[ET.Element],
    common_header: Optional[ET.Element],
    archive_path: Path,
    archive: ArchiveReader,
    header_format: Optional[str],
    extract_files_enabled: bool,
    try_path_reconstruct: bool,
    resolve_cg_path: Callable[[str], str],
) -> Path:
    """Write the full JSON record and a short Markdown summary."""
    report = build_metadata_report(
        root=root,
        common_header=common_header,
        archive_path=archive_path,
        archive=archive,
        header_format=header_format,
        extract_files_enabled=extract_files_enabled,
        try_path_reconstruct=try_path_reconstruct,
        resolve_cg_path=resolve_cg_path,
    )
    json_target = output.write_text(
        "metadata_report.json",
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )

    lines = [
        "# Metadata analysis report",
        "",
        f"- Archive: {report['archive']['input_name']}",
        f"- Size: {report['archive']['total_size_bytes']} bytes",
        f"- Header format: {report['archive']['header_format']}",
        f"- Catalog entries: {report['analysis']['catalog_item_count']}",
        f"- Payload ranges: {report['analysis']['payload_range_count']}",
        f"- Diagnostics: {report['analysis']['diagnostic_count']}",
        "",
        "## Diagnostics",
        "",
    ]
    if not report["diagnostics"]:
        lines.append(
            "No structural diagnostics detected. This does not prove every "
            "interpretation is semantically correct."
        )
    for item in report["diagnostics"]:
        lines.append(
            f"- **{item['code']}** "
            f"(item {item.get('item_index', 'n/a')}): {item['message']}"
        )
    lines.extend(
        [
            "",
            "The JSON report retains raw attributes, XML, and parsed range fields.",
            "Review and redact personal data before sharing.",
        ]
    )
    output.write_text_safely("metadata_report.md", "\n".join(lines) + "\n")
    return json_target
