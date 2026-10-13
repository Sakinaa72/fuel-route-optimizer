import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_postman_collection_requests_and_variables():
    collection = json.loads((ROOT / "postman/fuel-route-optimizer.postman_collection.json").read_text())
    variables = {item["key"] for item in collection["variable"]}
    assert collection["info"]["schema"].endswith("collection.json")
    assert len(collection["item"]) == 6
    for item in collection["item"]:
        request = item["request"]
        assert request["url"].startswith("{{base_url}}/api/v1/")
        for var in re.findall(r"\{\{(\w+)\}\}", json.dumps(request)):
            assert var in variables
        if "body" in request:
            json.loads(request["body"]["raw"])
        assert item["event"][0]["listen"] == "test"


def test_openapi_references_resolve():
    schema = json.loads((ROOT / "docs/openapi.json").read_text())

    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                pointer = value["$ref"]
                assert pointer.startswith("#/")
                target = schema
                for key in pointer[2:].split("/"):
                    target = target[key]
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)


def test_docker_files_reference_existing_sources():
    assert (ROOT / "scripts/docker-entrypoint.sh").exists()
    assert 'ENTRYPOINT ["sh", "/app/scripts/docker-entrypoint.sh"]' in (ROOT / "Dockerfile").read_text()
    assert "--require-hashes" in (ROOT / "Dockerfile").read_text()
    assert "./data:/app/input:ro" in (ROOT / "docker-compose.yml").read_text()
