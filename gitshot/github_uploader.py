"""Upload ảnh lên GitHub qua Contents API và trả về link trực tiếp.

Luồng chính của GitShot:
  chụp -> (sửa) -> Enter/Gửi -> PUT /repos/{owner}/{repo}/contents/{path}
  -> trả link raw (mở/embed được ngay) + tự copy vào clipboard.

Chỉ dùng thư viện chuẩn (urllib) để bản .exe nhẹ và ít lỗi đóng gói.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .utils import build_links, make_upload_path, sanitize_repo_name

API = "https://api.github.com"


class GitHubError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class UploadResult:
    path: str
    raw_url: str
    cdn_url: str
    page_url: str
    sha: str
    size: int

    def link(self, link_type: str = "raw") -> str:
        return self.cdn_url if link_type == "cdn" else self.raw_url


class GitHubUploader:
    def __init__(self, token: str, opener=None):
        self.token = (token or "").strip()
        # opener: callable(Request) -> (status, dict) — inject khi unit test
        self._opener = opener or self._default_opener

    # ---------- HTTP ----------
    def _default_opener(self, req: urllib.request.Request):
        import http.client
        # Timeout giãn theo kích thước dữ liệu gửi: file lớn không bị cắt ở 60s
        size = len(req.data) if req.data else 0
        timeout = min(300, 60 + size // (512 * 1024) * 30)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8") or "{}"
                return resp.status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace") or "{}"
            try:
                data = json.loads(body)
            except Exception:
                data = {"message": body}
            return e.code, data
        except urllib.error.URLError as e:
            raise GitHubError(f"Không kết nối được GitHub: {e.reason}") from e
        except (http.client.HTTPException, ConnectionError, TimeoutError, OSError) as e:
            # Rớt kết nối giữa chừng khi đọc phản hồi... -> lỗi thân thiện, cho phép retry
            raise GitHubError(f"Mất kết nối tới GitHub giữa chừng: {e}") from e

    def _request(self, method: str, url: str, payload: dict | None = None):
        if not self.token:
            raise GitHubError("Chưa nhập GitHub token. Vào Cài đặt → GitHub để thêm.")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "GitShot")
        # Retry lỗi tạm thời (mất mạng, 5xx) tối đa 3 lần với backoff tăng dần
        import time
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                status, body = self._opener(req)
                if status >= 500 and attempt < 2:
                    time.sleep(0.6 * (attempt + 1))
                    continue
                return status, body
            except GitHubError as e:
                last_err = e
                if attempt < 2:
                    time.sleep(0.6 * (attempt + 1))
        raise last_err or GitHubError("Không gọi được GitHub.")

    # ---------- Tài khoản / repo ----------
    def whoami(self) -> str:
        status, body = self._request("GET", f"{API}/user")
        if status != 200:
            raise GitHubError(_friendly(body, status), status)
        return body.get("login", "")

    def repo_exists(self, owner: str, repo: str) -> bool:
        status, body = self._request("GET", f"{API}/repos/{owner}/{repo}")
        if status == 200:
            return True
        if status in (401, 403):
            # Token sai/thiếu quyền KHÔNG đồng nghĩa repo không tồn tại —
            # báo đúng nguyên nhân thay vì đi tạo repo rồi lỗi khó hiểu.
            raise GitHubError(_friendly(body, status), status)
        return False

    def ensure_repo(self, owner: str, repo: str, private: bool = False) -> None:
        """Tạo repo chứa ảnh nếu chưa có (kèm README + thư mục uploads)."""
        repo = sanitize_repo_name(repo)
        if self.repo_exists(owner, repo):
            return
        status, body = self._request("POST", f"{API}/user/repos", {
            "name": repo,
            "description": "Ảnh chụp màn hình do GitShot tự động tải lên",
            "private": private,
            "auto_init": True,
        })
        if status not in (201, 200):
            raise GitHubError(_friendly(body, status), status)

    # ---------- Upload ----------
    def upload_bytes(
        self,
        data: bytes,
        filename: str,
        owner: str,
        repo: str,
        branch: str = "main",
        folder_pattern: str = "uploads/{yyyy}/{MM}",
        message: str | None = None,
        auto_create_repo: bool = True,
    ) -> UploadResult:
        if not owner:
            owner = self.whoami()
        repo = sanitize_repo_name(repo)
        if auto_create_repo:
            self.ensure_repo(owner, repo)
        path = make_upload_path(folder_pattern, filename)
        payload = {
            "message": message or f"GitShot: {filename}",
            "content": base64.b64encode(data).decode("ascii"),
            "branch": branch,
        }
        from urllib.parse import quote
        url = f"{API}/repos/{owner}/{repo}/contents/{quote(path, safe='/')}"
        status, body = self._request("PUT", url, payload)
        if status in (409, 422):
            # File trùng tên -> lấy sha rồi ghi bản mới (tên file nay đã chống
            # trùng theo mili-giây, nhánh này chỉ còn là lưới an toàn)
            s2, cur = self._request("GET", f"{url}?ref={quote(branch, safe='')}")
            if s2 == 200 and cur.get("sha"):
                payload["sha"] = cur["sha"]
                status, body = self._request("PUT", url, payload)
        if status not in (200, 201):
            raise GitHubError(_friendly(body, status), status)
        content = body.get("content") or {}
        links = build_links(owner, repo, branch, path)
        return UploadResult(
            path=path,
            raw_url=content.get("download_url") or links["raw"],
            cdn_url=links["cdn"],
            page_url=content.get("html_url") or links["page"],
            sha=content.get("sha", ""),
            size=len(data),
        )


def _friendly(body: dict, status: int) -> str:
    msg = (body or {}).get("message", "")
    if status == 401:
        return "Token GitHub không hợp lệ hoặc đã hết hạn (401). Tạo token mới rồi dán lại trong Cài đặt."
    if status == 403:
        return "GitHub từ chối quyền (403). Token cần quyền 'Contents: Read and write' trên repo chứa ảnh."
    if status == 404:
        return "Không thấy repo chứa ảnh (404). Kiểm tra tên repo hoặc bật 'Tự tạo repo khi chưa có'."
    return f"GitHub lỗi {status}: {msg or 'không rõ nguyên nhân'}"
