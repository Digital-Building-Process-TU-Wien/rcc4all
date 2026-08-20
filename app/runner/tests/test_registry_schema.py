from __future__ import annotations

from openbim_runner.nodes import get_registry_schema


def test_registry_schema_includes_node_readme_metadata() -> None:
    schema = get_registry_schema()

    concat_string_schema = schema["properties"]["concat_string"]
    assert concat_string_schema["title"] == "Concatenate Strings"
    assert (
        concat_string_schema["description"]
        == "Join a list of resolved string values into one output string."
    )
    assert "Use case example" in concat_string_schema["markdownDescription"]

    for node_name in ["concat_string", "ifc_element_filter", "get_name"]:
        node_schema = schema["properties"][node_name]
        assert node_schema["markdownDescription"]


def test_registry_schema_node_keys_are_sorted() -> None:
    schema = get_registry_schema()

    node_names = list(schema["properties"].keys())
    assert node_names == sorted(node_names)


def test_registry_schema_locales_are_sorted() -> None:
    schema = get_registry_schema()

    for node_schema in schema["properties"].values():
        locales = list(node_schema["locales"].keys())
        assert locales == sorted(locales), node_schema["title"]
        assert "en" in locales
