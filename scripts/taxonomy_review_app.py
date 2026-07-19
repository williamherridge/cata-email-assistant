"""Local web app for reviewing taxonomy discovery samples."""

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_ROOT = REPO_ROOT / "data" / "analytics" / "taxonomy_discovery"
TAXONOMY_CATALOG_PATH = REPO_ROOT / "data" / "analytics" / "taxonomy_catalog.json"
WEB_ROOT = REPO_ROOT / "web" / "taxonomy_review_app"


def parse_args():
    parser = argparse.ArgumentParser(description="Run the taxonomy review web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8008, help="Port to bind to.")
    return parser.parse_args()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def default_taxonomy_catalog():
    return {
        "updated_at": "",
        "categories": [],
    }


def load_taxonomy_catalog():
    if not TAXONOMY_CATALOG_PATH.exists():
        return default_taxonomy_catalog()

    try:
        payload = load_json(TAXONOMY_CATALOG_PATH)
    except (OSError, json.JSONDecodeError):
        return default_taxonomy_catalog()

    if not isinstance(payload, dict):
        return default_taxonomy_catalog()

    payload.setdefault("updated_at", "")
    payload.setdefault("categories", [])
    return payload


def write_taxonomy_catalog(catalog):
    TAXONOMY_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalog["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(TAXONOMY_CATALOG_PATH, catalog)


def discover_runs():
    runs = []
    if not DISCOVERY_ROOT.exists():
        return runs

    for run_dir in sorted(DISCOVERY_ROOT.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue

        manifest_paths = list(run_dir.glob("*_manifest.json"))
        if not manifest_paths:
            continue

        manifest_path = manifest_paths[0]
        try:
            manifest = load_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue

        runs.append(
            {
                "run_id": run_dir.name,
                "run_directory": str(run_dir.relative_to(REPO_ROOT)),
                "since": manifest.get("since", ""),
                "through": manifest.get("through", ""),
                "sample_size_written": manifest.get("sample_size_written", 0),
                "run_timestamp": manifest.get("run_timestamp", ""),
                "manifest_path": str(manifest_path.relative_to(REPO_ROOT)),
            }
        )
    return runs


def get_run_paths(run_id):
    run_dir = DISCOVERY_ROOT / run_id
    manifest_path = next(run_dir.glob("*_manifest.json"), None)
    sample_path = next(run_dir.glob("*_sample.json"), None)
    summary_path = next(run_dir.glob("*_summary.json"), None)
    if not run_dir.exists() or not manifest_path or not sample_path or not summary_path:
        raise FileNotFoundError(f"Run not found: {run_id}")
    return run_dir, manifest_path, sample_path, summary_path


def build_category_index(sample_rows):
    categories = {}
    subcategories = {}
    for row in sample_rows:
        category = (row.get("approved_category") or "").strip()
        subcategory = (row.get("approved_subcategory") or "").strip()
        if category:
            categories[category] = categories.get(category, 0) + 1
        if category and subcategory:
            key = f"{category}::{subcategory}"
            subcategories[key] = subcategories.get(key, 0) + 1
    return {
        "categories": [
            {"value": key, "count": count}
            for key, count in sorted(categories.items(), key=lambda item: (-item[1], item[0].lower()))
        ],
        "subcategories": [
            {
                "category": key.split("::", 1)[0],
                "value": key.split("::", 1)[1],
                "count": count,
            }
            for key, count in sorted(subcategories.items(), key=lambda item: (-item[1], item[0].lower()))
        ],
    }


def build_catalog_index(catalog):
    categories = []
    subcategories = []

    for category in catalog.get("categories", []):
        category_name = (category.get("name") or "").strip()
        if not category_name:
            continue

        aliases = category.get("aliases", [])
        categories.append(
            {
                "value": category_name,
                "count": category.get("usage_count", 0),
                "source": "catalog",
                "aliases": aliases,
            }
        )

        for subcategory in category.get("subcategories", []):
            subcategory_name = (subcategory.get("name") or "").strip()
            if not subcategory_name:
                continue

            subcategories.append(
                {
                    "category": category_name,
                    "value": subcategory_name,
                    "count": subcategory.get("usage_count", 0),
                    "source": "catalog",
                    "aliases": subcategory.get("aliases", []),
                }
            )

    categories.sort(key=lambda item: (-item["count"], item["value"].lower()))
    subcategories.sort(
        key=lambda item: (-item["count"], item["category"].lower(), item["value"].lower()),
    )
    return {"categories": categories, "subcategories": subcategories}


def merge_sample_into_catalog(catalog, sample_rows):
    categories_by_name = {}
    for category in catalog.get("categories", []):
        category_name = (category.get("name") or "").strip()
        if not category_name:
            continue
        category.setdefault("parent_group", "")
        category.setdefault("aliases", [])
        category.setdefault("subcategories", [])
        category.setdefault("usage_count", 0)
        categories_by_name[category_name] = category

    for row in sample_rows:
        category_name = (row.get("approved_category") or "").strip()
        subcategory_name = (row.get("approved_subcategory") or "").strip()
        if not category_name:
            continue

        category = categories_by_name.get(category_name)
        if category is None:
            category = {
                "name": category_name,
                "parent_group": "",
                "aliases": [],
                "subcategories": [],
                "usage_count": 0,
            }
            catalog["categories"].append(category)
            categories_by_name[category_name] = category

        category["usage_count"] += 1

        if not subcategory_name:
            continue

        existing_subcategory = None
        for subcategory in category["subcategories"]:
            if (subcategory.get("name") or "").strip() == subcategory_name:
                existing_subcategory = subcategory
                break

        if existing_subcategory is None:
            existing_subcategory = {
                "name": subcategory_name,
                "aliases": [],
                "usage_count": 0,
            }
            category["subcategories"].append(existing_subcategory)

        existing_subcategory["usage_count"] += 1

    catalog["categories"].sort(key=lambda item: item["name"].lower())
    for category in catalog["categories"]:
        category["subcategories"].sort(key=lambda item: item["name"].lower())
    return catalog


class TaxonomyReviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/runs":
            self.respond_json({"runs": discover_runs()})
            return

        if parsed.path == "/api/run":
            params = parse_qs(parsed.query)
            run_id = params.get("id", [""])[0]
            try:
                _, manifest_path, sample_path, summary_path = get_run_paths(run_id)
                manifest = load_json(manifest_path)
                sample = load_json(sample_path)
                summary = load_json(summary_path)
                catalog = load_taxonomy_catalog()
            except FileNotFoundError:
                self.respond_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            except (OSError, json.JSONDecodeError):
                self.respond_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not load run")
                return

            self.respond_json(
                {
                    "manifest": manifest,
                    "summary": summary,
                    "sample": sample,
                    "index": build_category_index(sample),
                    "catalog": catalog,
                    "catalog_index": build_catalog_index(catalog),
                }
            )
            return

        if parsed.path == "/api/taxonomy-catalog":
            self.respond_json({"catalog": load_taxonomy_catalog()})
            return

        self.serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/save-sample":
            payload = self.read_json_body()
            if payload is None:
                return

            run_id = payload.get("run_id", "")
            sample = payload.get("sample")
            if not run_id or not isinstance(sample, list):
                self.respond_error(HTTPStatus.BAD_REQUEST, "Missing run_id or sample")
                return

            try:
                _, _, sample_path, _ = get_run_paths(run_id)
                write_json(sample_path, sample)
                catalog = load_taxonomy_catalog()
                merged_catalog = merge_sample_into_catalog(catalog, sample)
                write_taxonomy_catalog(merged_catalog)
            except FileNotFoundError:
                self.respond_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            except OSError:
                self.respond_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not save sample")
                return

            saved_catalog = load_taxonomy_catalog()
            self.respond_json(
                {
                    "ok": True,
                    "index": build_category_index(sample),
                    "catalog": saved_catalog,
                    "catalog_index": build_catalog_index(saved_catalog),
                }
            )
            return

        if parsed.path == "/api/save-taxonomy-catalog":
            payload = self.read_json_body()
            if payload is None:
                return

            catalog = payload.get("catalog")
            if not isinstance(catalog, dict):
                self.respond_error(HTTPStatus.BAD_REQUEST, "Missing catalog payload")
                return

            try:
                write_taxonomy_catalog(catalog)
            except OSError:
                self.respond_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not save catalog")
                return

            saved_catalog = load_taxonomy_catalog()
            self.respond_json(
                {
                    "ok": True,
                    "catalog": saved_catalog,
                    "catalog_index": build_catalog_index(saved_catalog),
                }
            )
            return

        if parsed.path == "/api/promote-sample-labels":
            payload = self.read_json_body()
            if payload is None:
                return

            run_id = payload.get("run_id", "")
            if not run_id:
                self.respond_error(HTTPStatus.BAD_REQUEST, "Missing run_id")
                return

            try:
                _, _, sample_path, _ = get_run_paths(run_id)
                sample = load_json(sample_path)
                catalog = load_taxonomy_catalog()
                merged_catalog = merge_sample_into_catalog(catalog, sample)
                write_taxonomy_catalog(merged_catalog)
            except FileNotFoundError:
                self.respond_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            except (OSError, json.JSONDecodeError):
                self.respond_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Could not promote labels to catalog",
                )
                return

            saved_catalog = load_taxonomy_catalog()
            self.respond_json(
                {
                    "ok": True,
                    "catalog": saved_catalog,
                    "catalog_index": build_catalog_index(saved_catalog),
                }
            )
            return

        if parsed.path == "/api/normalize":
            payload = self.read_json_body()
            if payload is None:
                return

            run_id = payload.get("run_id", "")
            field = payload.get("field", "")
            old_value = payload.get("old_value", "")
            new_value = payload.get("new_value", "")
            category_scope = payload.get("category_scope", "")

            if field not in {"approved_category", "approved_subcategory"}:
                self.respond_error(HTTPStatus.BAD_REQUEST, "Invalid field")
                return

            try:
                _, _, sample_path, _ = get_run_paths(run_id)
                sample = load_json(sample_path)
            except FileNotFoundError:
                self.respond_error(HTTPStatus.NOT_FOUND, "Run not found")
                return
            except (OSError, json.JSONDecodeError):
                self.respond_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not load sample")
                return

            updated = 0
            for row in sample:
                if field == "approved_category":
                    if (row.get("approved_category") or "").strip() == old_value:
                        row["approved_category"] = new_value
                        updated += 1
                else:
                    category_matches = True
                    if category_scope:
                        category_matches = (row.get("approved_category") or "").strip() == category_scope
                    if category_matches and (row.get("approved_subcategory") or "").strip() == old_value:
                        row["approved_subcategory"] = new_value
                        updated += 1

            try:
                write_json(sample_path, sample)
            except OSError:
                self.respond_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not save sample")
                return

            self.respond_json(
                {
                    "ok": True,
                    "updated": updated,
                    "sample": sample,
                    "index": build_category_index(sample),
                }
            )
            return

        self.respond_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            return json.loads(raw_body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self.respond_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
            return None

    def serve_static(self, path):
        if path in {"/", ""}:
            path = "/index.html"

        target = (WEB_ROOT / path.lstrip("/")).resolve()
        if not str(target).startswith(str(WEB_ROOT.resolve())) or not target.exists():
            self.respond_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        content_type, _ = mimetypes.guess_type(str(target))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def respond_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_error(self, status, message):
        self.respond_json({"error": message}, status=status)

    def log_message(self, format, *args):
        return


def main():
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), TaxonomyReviewHandler)
    print(f"Taxonomy review app running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
