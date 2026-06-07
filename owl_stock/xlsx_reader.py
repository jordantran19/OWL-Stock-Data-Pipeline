"""Read .xlsx files that use the strict OOXML namespace (openpyxl/pandas miss sheets)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

_NS = {"main": "http://purl.oclc.org/ooxml/spreadsheetml/main"}


def _col_letters(cell_ref: str) -> str:
    return "".join(ch for ch in cell_ref if ch.isalpha())


def read_sheet_rows(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(".//main:si", _NS):
                text_node = item.find("main:t", _NS)
                if text_node is not None and text_node.text:
                    shared.append(text_node.text)
                else:
                    shared.append(
                        "".join(
                            node.text or ""
                            for node in item.findall(".//main:t", _NS)
                        )
                    )

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[dict[str, str]] = []
        for row in sheet.findall("main:sheetData/main:row", _NS):
            cells: dict[str, str] = {}
            for cell in row.findall("main:c", _NS):
                value_node = cell.find("main:v", _NS)
                if value_node is None or value_node.text is None:
                    continue
                raw = value_node.text
                if cell.get("t") == "s":
                    raw = shared[int(raw)]
                cells[_col_letters(cell.get("r", ""))] = raw
            rows.append(cells)
    return rows


def sheet_to_records(path: str | Path) -> list[dict[str, str]]:
    rows = read_sheet_rows(path)
    if not rows:
        return []
    columns = sorted(rows[0].keys(), key=lambda key: (len(key), key))
    headers = [rows[0][column] for column in columns]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        records.append(
            {headers[index]: row.get(columns[index], "") for index in range(len(headers))}
        )
    return records
