"""Machine-readable metadata reports for format research."""
import json

def _node(element):
    return {"tag": element.tag, "attributes": dict(element.attrib), "text": (element.text or "").strip() or None, "children": [_node(child) for child in list(element)]}

def build_metadata_report(extractor):
    entries = []
    diagnostics = []
    root = extractor.root
    if root is not None:
        for index, item in enumerate(root.findall("BackupItem")):
            category = item.get("Category", "UNKNOWN")
            attrs = dict(item.attrib)
            raw_offset, raw_size = attrs.get("StartOffset"), attrs.get("DataSize")
            try:
                offset = int(raw_offset) if raw_offset is not None else None
                size = int(raw_size) if raw_size is not None else None
                valid = offset is not None and size is not None and offset >= 0 and size >= 0 and offset + size <= extractor.total_size
                status = "valid" if valid else "invalid_or_out_of_bounds"
            except (TypeError, ValueError):
                offset = size = None
                status = "unparsed_numeric_field"
            original = attrs.get("FileName") or category
            resolved, resolution = original, "not_applicable"
            if "_CG_" in category:
                resolved = extractor.resolve_cg_path(category) if extractor.try_path_reconstruct else category
                resolution = "resolved" if resolved != category else "unresolved"
                if resolution == "unresolved":
                    diagnostics.append({"code": "unresolved_cg_path", "item_index": index, "category": category, "message": "Path reference could not be reconstructed."})
            if status != "valid":
                diagnostics.append({"code": status, "item_index": index, "category": category, "start_offset_raw": raw_offset, "data_size_raw": raw_size, "message": "Offset/size is missing, malformed, negative, or outside archive bounds."})
            entries.append({"index": index, "category": category, "attributes": attrs, "start_offset_raw": raw_offset, "start_offset": offset, "data_size_raw": raw_size, "data_size": size, "range_status": status, "path_resolution": {"input": original, "resolved": resolved, "status": resolution}, "xml": _node(item)})
    common = extractor.common_header
    return {"report_schema_version": 1, "tool": {"name": "lbf-extractor", "version": "1.3.0"}, "archive": {"input_name": extractor.archive_path.name, "total_size_bytes": extractor.total_size, "segments": [{"name": p.name, "size_bytes": p.stat().st_size} for p in extractor.part_paths], "header_format": extractor.header_format}, "analysis": {"catalog_item_count": len(entries), "diagnostic_count": len(diagnostics), "extract_files_enabled": extractor.extract_files_enabled}, "common_metadata": _node(common) if common is not None else None, "catalog_items": entries, "diagnostics": diagnostics, "full_header_tree": _node(root) if root is not None else None, "sharing_guidance": "Redact personal identifiers, paths, contacts, and message metadata before sharing."}

def write_metadata_report(extractor):
    extractor.output_dir.mkdir(parents=True, exist_ok=True)
    report = build_metadata_report(extractor)
    target = extractor.output_dir / "metadata_report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Metadata analysis report", "", f"- Archive: {report['archive']['input_name']}", f"- Size: {report['archive']['total_size_bytes']} bytes", f"- Header format: {report['archive']['header_format']}", f"- Catalog entries: {report['analysis']['catalog_item_count']}", f"- Diagnostics: {report['analysis']['diagnostic_count']}", "", "## Diagnostics", ""]
    if not report["diagnostics"]:
        lines.append("No structural diagnostics detected; this does not prove every interpretation is semantically correct.")
    for item in report["diagnostics"]:
        lines.append(f"- **{item['code']}** (item {item.get('item_index', 'n/a')}): {item['message']}")
    lines.extend(["", "Full raw fields and parsed XML are in metadata_report.json.", "Review and redact personal data before sharing."])
    (extractor.output_dir / "metadata_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
