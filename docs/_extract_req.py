# -*- coding: utf-8 -*-
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

path = Path(__file__).with_name("req_trabajo.xlsx")
out_path = Path(__file__).with_name("_req_dump.json")

wb = openpyxl.load_workbook(path, data_only=True)
sheets = [
    "ReqFunBackend",
    "ReqNoFunBackend",
    "ReqFunFrontend",
    "ReqNoFunFrontend",
    "ReqFunBD",
    "ReqNoFunDB",
]

data = {}
duplicates = {}

for name in sheets:
    ws = wb[name]
    rows = []
    seen = defaultdict(list)
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
        vals = [str(c).strip() if c is not None else "" for c in row]
        if not any(vals):
            continue
        rows.append({"row": row_idx, "cells": vals})
        role = vals[0] if len(vals) > 0 else ""
        num = vals[1] if len(vals) > 1 else ""
        desc = vals[2] if len(vals) > 2 else ""
        if num.isdigit() and desc:
            key = re.sub(r"\s+", " ", desc.lower())
            seen[key].append({"row": row_idx, "num": num, "role": role, "desc": desc})
    data[name] = rows
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    if dups:
        duplicates[name] = dups

payload = {"sheets": data, "duplicates": duplicates}
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(out_path)
