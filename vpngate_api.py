#!/usr/bin/env python3
"""Shared validation helpers for the VPNGate CSV API."""

from __future__ import annotations

import csv


REQUIRED_COLUMNS = {
    "HostName",
    "IP",
    "CountryLong",
    "CountryShort",
    "OpenVPN_ConfigData_Base64",
}


class VPNGateAPIResponseError(ValueError):
    """Raised when an HTTP success response is not a usable VPNGate CSV."""


def build_api_request_headers(user_agent: str, token: str = "") -> dict[str, str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/plain,*/*",
    }
    if token:
        if "\r" in token or "\n" in token:
            raise ValueError("API token must not contain line breaks")
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_vpngate_csv(text: str) -> list[dict[str, str]]:
    if not isinstance(text, str) or not text.strip():
        raise VPNGateAPIResponseError("[ERR_API_EMPTY_RESPONSE] VPNGate API 返回了空响应。")

    stripped = text.lstrip("\ufeff\r\n\t ")
    lower_prefix = stripped[:256].lower()
    if lower_prefix.startswith("<!doctype html") or lower_prefix.startswith("<html"):
        raise VPNGateAPIResponseError(
            "[ERR_API_HTML_RESPONSE] API 返回了 HTML 而不是节点 CSV；"
            "该出口 IP 可能被 VPNGate 限流或限制。"
        )

    source_lines = text.splitlines()
    header_index = next(
        (index for index, line in enumerate(source_lines) if line.lstrip("\ufeff").startswith("#HostName,")),
        None,
    )
    if header_index is None:
        raise VPNGateAPIResponseError(
            "[ERR_API_INVALID_RESPONSE] 响应中缺少 VPNGate CSV 表头。"
        )

    csv_lines = [source_lines[header_index].lstrip("\ufeff")[1:]]
    for line in source_lines[header_index + 1 :]:
        if line.startswith("*"):
            break
        if line:
            csv_lines.append(line)

    reader = csv.DictReader(csv_lines)
    fieldnames = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - fieldnames
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise VPNGateAPIResponseError(
            f"[ERR_API_INVALID_RESPONSE] VPNGate CSV 缺少必要字段: {missing_text}"
        )

    rows: list[dict[str, str]] = []
    for raw_row in reader:
        row: dict[str, str] = {
            str(key): str(value or "")
            for key, value in raw_row.items()
            if key is not None
        }
        if row.get("IP") and row.get("OpenVPN_ConfigData_Base64"):
            rows.append(row)

    if not rows:
        raise VPNGateAPIResponseError(
            "[ERR_API_NO_NODES] VPNGate CSV 格式有效，但没有包含可用的 OpenVPN 节点记录。"
        )
    return rows


def validate_vpngate_csv(text: str) -> int:
    """Validate a response and return its usable node count."""

    return len(parse_vpngate_csv(text))
