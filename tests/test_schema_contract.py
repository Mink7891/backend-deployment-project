"""Generated DTOs retain the approved wire names and monetary constraints."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import app.schemas as public_schemas
from app.schemas import game_radar_api as generated

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "doc" / "game-radar-api.yaml").read_text(
        encoding="utf-8"
    )
)
COMPONENTS = CONTRACT["components"]["schemas"]
OBJECT_NAMES = [
    name
    for name, schema in COMPONENTS.items()
    if schema.get("type") == "object" or "allOf" in schema
]


def contract_fields(schema):
    properties = dict(schema.get("properties", {}))
    required = set(schema.get("required", []))
    for part in schema.get("allOf", []):
        if "$ref" in part:
            part = COMPONENTS[part["$ref"].rsplit("/", 1)[1]]
        nested_properties, nested_required = contract_fields(part)
        properties.update(nested_properties)
        required.update(nested_required)
    return properties, required


@pytest.mark.parametrize("name", OBJECT_NAMES)
def test_generated_dtos_preserve_approved_aliases_required_fields_and_extra_rules(name):
    model = getattr(generated, name)
    schema = model.model_json_schema(by_alias=True, mode="serialization")
    properties, required = contract_fields(COMPONENTS[name])
    assert schema["properties"].keys() == properties.keys()
    assert set(schema.get("required", [])) == required
    assert schema["additionalProperties"] is False
    assert model.model_config["populate_by_name"] is True
    assert model.model_config["frozen"] is True
    assert all("_" not in name for name in schema["properties"])


def test_public_http_dtos_use_the_generated_contract_classes():
    for name in OBJECT_NAMES:
        if name not in {"ProblemDetails", "ValidationProblemDetails", "ValidationIssue"}:
            assert getattr(public_schemas, name) is getattr(generated, name)


@pytest.mark.parametrize("wire_name", ["targetPrice", "target_price"])
@pytest.mark.parametrize("value", ["0", "0.01", "9999999999.99", 4])
def test_generated_money_request_accepts_boundary_values_with_either_input_alias(wire_name, value):
    request = generated.AddItemRequest.model_validate({"gameId": "612", wire_name: value})
    assert request.target_price == Decimal(str(value))
    assert isinstance(request.target_price, Decimal)
    assert request.steam_only is True
    wire = json.loads(request.model_dump_json())
    assert set(wire) == {"gameId", "targetPrice", "steamOnly"}
    assert wire["targetPrice"] == str(Decimal(str(value)))


@pytest.mark.parametrize("value", ["-0.01", "1.001", "10000000000", "NaN", "Infinity"])
def test_generated_money_request_rejects_values_outside_approved_limits(value):
    with pytest.raises(ValidationError):
        generated.AddItemRequest(gameId="612", targetPrice=value)


@pytest.mark.parametrize("body", [{}, {"targetPrice": None}, {"steamOnly": None}])
def test_generated_patch_retains_nonempty_and_nonnull_cross_field_rules(body):
    with pytest.raises(ValidationError):
        generated.UpdateItemRequest.model_validate(body)


def test_generated_models_retain_handwritten_name_normalization_and_reject_unknown_fields():
    assert generated.CreateWatchlistRequest(name="  Wishlist  ").name == "Wishlist"
    with pytest.raises(ValidationError):
        generated.CreateWatchlistRequest(name="   ")
    with pytest.raises(ValidationError):
        generated.AddItemRequest(gameId="612", targetPrice="4.00", password="private")


def test_generated_price_response_serializes_exact_decimal_strings():
    response = generated.SummaryResponse(
        watchlistId=1,
        totalItems=2,
        pricedItems=2,
        matchedCount=1,
        currentTotal=Decimal("12345678901234567890.01"),
        currency="USD",
        source="mock",
    )
    assert isinstance(response.current_total, Decimal)
    assert json.loads(response.model_dump_json())["currentTotal"] == "12345678901234567890.01"
    with pytest.raises(ValidationError):
        generated.SummaryResponse.model_validate({**response.model_dump(), "currency": "EUR"})


def test_runtime_openapi_documents_problem_media_type_and_canonical_success_fields(client):
    schema = client.get("/openapi.json").json()
    for path, methods in CONTRACT["paths"].items():
        for method, operation in methods.items():
            runtime = schema["paths"][path][method]
            for status, expected in operation["responses"].items():
                assert status in runtime["responses"], (method, path, status)
                if int(status) >= 400:
                    assert set(runtime["responses"][status]["content"]) == {
                        "application/problem+json"
                    }
                    actual_problem = runtime["responses"][status]["content"][
                        "application/problem+json"
                    ]["schema"]
                    expected_problem = expected["content"]["application/problem+json"]["schema"]
                    expected_name = expected_problem["$ref"].rsplit("/", 1)[1]
                    properties, required = contract_fields(COMPONENTS[expected_name])
                    if "$ref" in actual_problem:
                        actual_problem = schema["components"]["schemas"][
                            actual_problem["$ref"].rsplit("/", 1)[1]
                        ]
                    assert actual_problem["properties"].keys() == properties.keys()
                    assert set(actual_problem["required"]) == required
                elif "content" in expected:
                    actual_ref = runtime["responses"][status]["content"]["application/json"][
                        "schema"
                    ]
                    expected_ref = expected["content"]["application/json"]["schema"]
                    assert actual_ref.get("$ref") == expected_ref.get("$ref")
    for name in OBJECT_NAMES:
        if name in {"ProblemDetails", "ValidationProblemDetails", "ValidationIssue"}:
            # Error response utilities can inline equivalent Problem Details schemas.
            continue
        properties, required = contract_fields(COMPONENTS[name])
        actual = schema["components"]["schemas"][name]
        assert actual["properties"].keys() == properties.keys()
        assert set(actual.get("required", [])) == required
