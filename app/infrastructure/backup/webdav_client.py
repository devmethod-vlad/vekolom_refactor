from __future__ import annotations

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx


logger = logging.getLogger("app.backup")


@dataclass(slots=True)
class RemoteEntry:
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    modified_at: datetime | None = None


class WebDavClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: int,
        verify_tls: bool,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            auth=(username, password),
            timeout=timeout_seconds,
            verify=verify_tls,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WebDavClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _normalize_remote_path(self, remote_path: str) -> str:
        return "/" + remote_path.strip("/") if remote_path else "/"

    def _build_url(self, remote_path: str) -> str:
        normalized = self._normalize_remote_path(remote_path)
        quoted = urllib.parse.quote(normalized, safe="/")
        return f"{self.base_url}{quoted}"

    def exists(self, remote_path: str) -> bool:
        response = self._client.request("HEAD", self._build_url(remote_path))
        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            response.raise_for_status()
        return True

    def ensure_remote_dir(self, remote_dir: str) -> None:
        current = ""
        for chunk in self._normalize_remote_path(remote_dir).strip("/").split("/"):
            current = f"{current}/{chunk}" if current else f"/{chunk}"
            response = self._client.request("MKCOL", self._build_url(current))
            if response.status_code in (201, 405):
                continue
            if response.status_code == 409:
                # parent path is missing due to server specifics; continue loop
                continue
            response.raise_for_status()

    def upload_file(self, local_path, remote_path: str) -> None:
        with open(local_path, "rb") as file_stream:
            response = self._client.put(
                self._build_url(remote_path),
                content=file_stream,
                headers={"Content-Type": "application/octet-stream"},
            )
        if response.status_code >= 400:
            response.raise_for_status()

    def delete_file(self, remote_path: str) -> None:
        response = self._client.delete(self._build_url(remote_path))
        if response.status_code in (200, 204, 404):
            return
        response.raise_for_status()

    def list_dir(self, remote_dir: str) -> list[RemoteEntry]:
        body = """<?xml version=\"1.0\" encoding=\"utf-8\" ?>
<d:propfind xmlns:d=\"DAV:\">
  <d:prop>
    <d:resourcetype />
    <d:getcontentlength />
    <d:getlastmodified />
  </d:prop>
</d:propfind>"""
        response = self._client.request(
            "PROPFIND",
            self._build_url(remote_dir),
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=body,
        )
        if response.status_code >= 400:
            response.raise_for_status()

        return self._parse_propfind_response(response.text, remote_dir)

    def _parse_propfind_response(self, body: str, remote_dir: str) -> list[RemoteEntry]:
        namespace = {"d": "DAV:"}
        root = ET.fromstring(body)
        entries: list[RemoteEntry] = []
        normalized_remote_dir = self._normalize_remote_path(remote_dir).rstrip("/")

        for item in root.findall("d:response", namespace):
            href = item.findtext("d:href", default="", namespaces=namespace)
            if not href:
                continue

            unquoted = urllib.parse.unquote(urllib.parse.urlparse(href).path).rstrip("/")
            if unquoted == normalized_remote_dir:
                continue

            name = unquoted.split("/")[-1]
            prop = item.find("d:propstat/d:prop", namespace)
            if prop is None:
                continue

            is_dir = prop.find("d:resourcetype/d:collection", namespace) is not None
            size_text = prop.findtext("d:getcontentlength", default=None, namespaces=namespace)
            modified_text = prop.findtext("d:getlastmodified", default=None, namespaces=namespace)
            modified_at = None
            if modified_text:
                try:
                    modified_at = parsedate_to_datetime(modified_text)
                except (TypeError, ValueError):
                    logger.warning("Cannot parse modified date from WebDAV: %s", modified_text)

            entries.append(
                RemoteEntry(
                    name=name,
                    path=unquoted,
                    is_dir=is_dir,
                    size=int(size_text) if size_text and size_text.isdigit() else None,
                    modified_at=modified_at,
                )
            )

        return entries
