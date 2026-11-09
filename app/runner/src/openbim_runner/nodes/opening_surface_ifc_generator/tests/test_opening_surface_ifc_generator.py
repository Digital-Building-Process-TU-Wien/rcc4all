from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import ifcopenshell
import pytest

from conftest import main_ref
from openbim_runner.inspect_models import MODELS_ROOT
from openbim_runner.nodes.base import ExecutionContext
from openbim_runner.nodes.opening_surface.opening_surface import (
    OpeningSurface,
    OpeningSurfaceInputs,
    opening_surface,
)
from openbim_runner.nodes.opening_surface_ifc_generator.opening_surface_ifc_generator import (
    OpeningSurfaceIfcGeneratorInputs,
    OpeningSurfaceIfcGeneratorResult,
    OpeningSurfaceIfcGeneratorSettings,
    opening_surface_ifc_generator,
)
from openbim_runner.util.geometry import build_geometry_cache

_REAL_MODEL = MODELS_ROOT / "specific" / "Testmodell-LightExposureSmall.ifc"


def _run(
    settings: OpeningSurfaceIfcGeneratorSettings,
    inputs: OpeningSurfaceIfcGeneratorInputs,
    context: ExecutionContext,
) -> OpeningSurfaceIfcGeneratorResult:
    return asyncio.run(opening_surface_ifc_generator(settings, inputs, context))


# --- real model -------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_context(tmp_path_factory: pytest.TempPathFactory) -> ExecutionContext:
    model = ifcopenshell.open(str(_REAL_MODEL))
    return ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
        output_dir=tmp_path_factory.mktemp("out"),
    )


@pytest.fixture(scope="module")
def real_openings(real_context: ExecutionContext) -> list[OpeningSurface]:
    model = cast(Any, real_context.ifc_model)
    host_refs = [
        f"main:expr:{entity.id()}"
        for entity_type in ("IfcWall", "IfcSlab", "IfcRoof")
        for entity in model.by_type(entity_type)
    ]
    result = asyncio.run(
        opening_surface(OpeningSurfaceInputs(express_ids=host_refs), real_context)
    )
    return result.openings


def _run_real(
    real_context: ExecutionContext, openings: list[OpeningSurface]
) -> OpeningSurfaceIfcGeneratorResult:
    return _run(
        OpeningSurfaceIfcGeneratorSettings(output_filename="result.ifc"),
        OpeningSurfaceIfcGeneratorInputs(openings=openings),
        real_context,
    )


def _expected_proxy_count(openings: list[OpeningSurface]) -> int:
    """Both caps of a through-opening become independent proxies."""
    return sum(2 if opening.depth is not None else 1 for opening in openings)


def test_real_model_generates_one_proxy_per_cap_face(
    real_context: ExecutionContext, real_openings: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_openings)

    expected = _expected_proxy_count(real_openings)
    assert Path(result.output_path).exists()
    assert result.element_count == expected
    assert len(result.elements) == expected
    assert all(element.error is None for element in result.elements)

    caps_per_opening: dict[str, list[int]] = {}
    for element in result.elements:
        caps_per_opening.setdefault(element.opening_ref, []).append(element.cap)
    for opening in real_openings:
        caps = caps_per_opening[opening.express_id]
        if opening.depth is None:
            assert caps == [0]
        else:
            assert sorted(caps) == [0, 1]


def test_real_model_replicates_storeys_and_containment(
    real_context: ExecutionContext, real_openings: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_openings)

    model = ifcopenshell.open(result.output_path)
    storeys = model.by_type("IfcBuildingStorey")
    containment = model.by_type("IfcRelContainedInSpatialStructure")

    assert result.storey_count > 0
    assert result.storey_count == len(storeys)
    assert len(containment) == _expected_proxy_count(real_openings)
    contained_ids = {rel.RelatingStructure.id() for rel in containment}
    assert contained_ids == {storey.id() for storey in storeys}
    assert all(element.storey_ref is not None for element in result.elements)


def test_real_model_proxies_have_tessellated_body(
    real_context: ExecutionContext, real_openings: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_openings)
    model = ifcopenshell.open(result.output_path)

    proxies = model.by_type("IfcBuildingElementProxy")
    assert len(proxies) == _expected_proxy_count(real_openings)
    assert {proxy.Name for proxy in proxies} == {"OpeningSurface_0", "OpeningSurface_1"}
    for proxy in proxies:
        shape = proxy.Representation
        assert shape is not None
        body = [
            rep
            for rep in shape.Representations
            if rep.RepresentationIdentifier == "Body"
        ]
        assert len(body) == 1
        assert body[0].RepresentationType == "Tessellation"
        assert len(body[0].Items) == 1
        assert body[0].Items[0].is_a("IfcPolygonalFaceSet")


def test_real_model_assigns_area_quantity(
    real_context: ExecutionContext, real_openings: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_openings)
    model = ifcopenshell.open(result.output_path)

    quantities = model.by_type("IfcQuantityArea")
    assert len(quantities) == _expected_proxy_count(real_openings)
    quantity_values = {round(quantity.AreaValue, 6) for quantity in quantities}
    opening_areas = {round(opening.area or 0.0, 6) for opening in real_openings}
    assert quantity_values == opening_areas
    assert len(model.by_type("IfcPropertySet")) == 0


def test_real_model_proxy_placed_at_world_origin(
    real_context: ExecutionContext, real_openings: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_openings)
    model = ifcopenshell.open(result.output_path)

    proxy = model.by_type("IfcBuildingElementProxy")[0]
    placement = proxy.ObjectPlacement
    assert placement.PlacementRelTo is None
    assert tuple(placement.RelativePlacement.Location.Coordinates) == (0.0, 0.0, 0.0)


# --- input validation -------------------------------------------------------------


def test_missing_openings_raises(real_context: ExecutionContext) -> None:
    with pytest.raises(ValueError, match="requires openings"):
        _run(
            OpeningSurfaceIfcGeneratorSettings(),
            OpeningSurfaceIfcGeneratorInputs(openings=[]),
            real_context,
        )


def test_missing_output_dir_raises(real_openings: list[OpeningSurface]) -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, ifcopenshell.open(str(_REAL_MODEL))),
        node_outputs={},
        geometry_cache={},
    )
    with pytest.raises(ValueError, match="requires an output directory"):
        _run(
            OpeningSurfaceIfcGeneratorSettings(),
            OpeningSurfaceIfcGeneratorInputs(openings=real_openings),
            context,
        )


def test_opening_without_geometry_is_reported(real_context: ExecutionContext) -> None:
    broken = OpeningSurface(
        express_id=main_ref(999),
        guid="broken",
        host_express_id=main_ref(1),
        error="no cached geometry",
    )
    result = _run_real(real_context, [broken])

    assert result.element_count == 0
    assert len(result.elements) == 1
    assert result.elements[0].error == "no cached geometry"
    assert result.elements[0].element_guid == ""
