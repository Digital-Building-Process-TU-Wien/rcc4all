from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import ifcopenshell
import pytest

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


@pytest.fixture(scope="module")
def real_context(tmp_path_factory: pytest.TempPathFactory) -> ExecutionContext:
    model = ifcopenshell.open(str(_REAL_MODEL))
    return ExecutionContext(
        ifc_model=cast(Any, model),
        node_outputs={},
        geometry_cache=build_geometry_cache(model),
        output_dir=tmp_path_factory.mktemp("out"),
    )


def _host_refs(model: Any) -> list[str]:
    return [
        f"main:expr:{entity.id()}"
        for entity_type in ("IfcWall", "IfcSlab", "IfcRoof")
        for entity in model.by_type(entity_type)
    ]


@pytest.fixture(scope="module")
def real_volumes(real_context: ExecutionContext) -> list[OpeningSurface]:
    model = cast(Any, real_context.ifc_model)
    result = asyncio.run(
        opening_surface(
            OpeningSurfaceInputs(express_ids=_host_refs(model)), real_context
        )
    )
    return result.openings


def _run_real(
    real_context: ExecutionContext, volumes: list[OpeningSurface]
) -> OpeningSurfaceIfcGeneratorResult:
    return _run(
        OpeningSurfaceIfcGeneratorSettings(output_filename="result.ifc"),
        OpeningSurfaceIfcGeneratorInputs(openings=volumes),
        real_context,
    )


def test_real_model_generates_one_proxy_per_opening(
    real_context: ExecutionContext, real_volumes: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_volumes)

    assert Path(result.output_path).exists()
    assert result.element_count == len(real_volumes)
    assert len(result.elements) == len(real_volumes)
    assert all(element.error is None for element in result.elements)
    assert [element.opening_ref for element in result.elements] == [
        opening.express_id for opening in real_volumes
    ]


def test_real_model_proxies_have_tessellated_body(
    real_context: ExecutionContext, real_volumes: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_volumes)
    model = ifcopenshell.open(result.output_path)

    proxies = model.by_type("IfcBuildingElementProxy")
    assert len(proxies) == len(real_volumes)
    for proxy in proxies:
        assert proxy.Name.startswith("OpeningSurface_")
        shape = proxy.Representation
        assert shape is not None
        body = [
            rep
            for rep in shape.Representations
            if rep.RepresentationIdentifier == "Body"
        ]
        assert len(body) == 1
        assert body[0].RepresentationType == "Tessellation"
        assert len(body[0].Items) >= 1
        assert all(item.is_a("IfcPolygonalFaceSet") for item in body[0].Items)
        assert all(len(item.Faces) > 0 for item in body[0].Items)


def test_real_model_assigns_volume_and_area_quantities(
    real_context: ExecutionContext, real_volumes: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_volumes)
    model = ifcopenshell.open(result.output_path)

    volume_quantities = model.by_type("IfcQuantityVolume")
    assert len(volume_quantities) == len(real_volumes)
    for quantity in volume_quantities:
        assert quantity.VolumeValue > 0

    area_quantities = model.by_type("IfcQuantityArea")
    assert len(area_quantities) == len(real_volumes)


def test_real_model_replicates_storeys_and_containment(
    real_context: ExecutionContext, real_volumes: list[OpeningSurface]
) -> None:
    result = _run_real(real_context, real_volumes)
    model = ifcopenshell.open(result.output_path)

    storeys = model.by_type("IfcBuildingStorey")
    containment = model.by_type("IfcRelContainedInSpatialStructure")

    assert result.storey_count > 0
    assert result.storey_count == len(storeys)
    assert len(containment) == len(real_volumes)
    contained_ids = {rel.RelatingStructure.id() for rel in containment}
    assert contained_ids == {storey.id() for storey in storeys}
    assert all(element.storey_ref is not None for element in result.elements)


# --- input validation -------------------------------------------------------------


def test_missing_openings_raises(real_context: ExecutionContext) -> None:
    with pytest.raises(ValueError, match="requires openings"):
        _run(
            OpeningSurfaceIfcGeneratorSettings(),
            OpeningSurfaceIfcGeneratorInputs(openings=[]),
            real_context,
        )


def test_missing_output_dir_raises(real_volumes: list[OpeningSurface]) -> None:
    context = ExecutionContext(
        ifc_model=cast(Any, ifcopenshell.open(str(_REAL_MODEL))),
        node_outputs={},
        geometry_cache={},
    )
    with pytest.raises(ValueError, match="requires an output directory"):
        _run(
            OpeningSurfaceIfcGeneratorSettings(),
            OpeningSurfaceIfcGeneratorInputs(openings=real_volumes),
            context,
        )


def test_opening_without_geometry_is_reported(real_context: ExecutionContext) -> None:
    broken = OpeningSurface(
        express_id="main:expr:999",
        guid="broken",
        host_express_id="main:expr:1",
        error="no cached geometry",
    )
    result = _run_real(real_context, [broken])

    assert result.element_count == 0
    assert len(result.elements) == 1
    assert result.elements[0].error == "no cached geometry"
    assert result.elements[0].element_guid == ""
