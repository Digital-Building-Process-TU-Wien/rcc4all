"""Qualified element references and geometry cache keys.

References on the wire are fully qualified: an IFC element is
``<slug>:expr:<id>``, generated geometry is ``gen:<object_id>``, and a GUID is
``<slug>:guid:<GUID>``. A reference names its own model, so consumers never
need a separate ``model_slug`` input.

``inter:`` keys (internal helper geometry) are valid geometry cache keys but
not element references: they can be resolved from the cache, but never parsed
into an IFC entity.

This module owns the key primitives (``expr_key``, ``split_expr_key``) so the
dependency direction stays one-way: ``util.geometry`` imports from here, never
the reverse.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openbim_runner.nodes.base import ExecutionContext

EXPR_KIND = "expr"
GEN_KIND = "gen"
GUID_KIND = "guid"

_EXPR_MARKER = ":expr:"
_GEN_PREFIX = "gen:"
_GUID_MARKER = ":guid:"
_INTER_PREFIX = "inter:"


def expr_key(slug: str, express_id: int) -> str:
    """Geometry-cache key for an IFC entity: ``<slug>:expr:<express_id>``."""
    return f"{slug}:expr:{express_id}"


def split_expr_key(key: str) -> tuple[str, int] | None:
    """Split an express-key ``<slug>:expr:<id>`` into ``(slug, express_id)``.

    Returns ``None`` for keys that are not IFC express keys (e.g. ``gen:`` or
    ``inter:`` keys).
    """
    marker = _EXPR_MARKER
    start = key.find(marker)
    if start <= 0:
        return None
    slug = key[:start]
    try:
        return slug, int(key[start + len(marker) :])
    except ValueError:
        return None


@dataclass(frozen=True)
class ElementRef:
    """A parsed IFC element reference: which model and which express id it names.

    ``reference`` keeps the original qualified string so results can echo it.
    """

    reference: str
    slug: str
    express_id: int


def expand_reference(reference: str) -> list[ElementRef]:
    """Expand a measurement/generator reference into IFC element refs.

    Handles the reference shapes a numeric checking node can carry through as
    its element identity:

    - Direct expr ref ``<slug>:expr:<id>`` -> single ``ElementRef``.
    - Collision intersection ``inter:intersection_<k1>_<k2>`` -> both member
      keys, when each side is an IFC express key.
    - Distance pair ``<k1>_<k2>`` (both sides ``:expr:``) -> both member keys.

    Any other shape (``gen:``, malformed, or a pair whose inner keys are not
    IFC express keys) yields ``[]``; the consumer then drops the reference.
    """
    reference = reference.strip()

    # Collision intersection — strip the helper prefix, fall through to pair split.
    remainder = reference
    if reference.startswith("inter:intersection_"):
        remainder = reference[len("inter:intersection_") :]

    # Direct single ref (only when no prefix was stripped).
    if remainder is reference:
        parsed = split_expr_key(reference)
        if parsed is not None:
            slug, express_id = parsed
            return [ElementRef(reference, slug, express_id)]

    # Pair ref: split on the last underscore between two express keys.
    underscore_pos = remainder.rfind("_")
    if underscore_pos > 0:
        k1 = remainder[:underscore_pos]
        k2 = remainder[underscore_pos + 1 :]
        parsed_k1 = split_expr_key(k1)
        parsed_k2 = split_expr_key(k2)
        if parsed_k1 is not None and parsed_k2 is not None:
            slug1, id1 = parsed_k1
            slug2, id2 = parsed_k2
            return [
                ElementRef(k1, slug1, id1),
                ElementRef(k2, slug2, id2),
            ]

    return []


def parse_element_ref(reference: str, *, node: str) -> ElementRef:
    """Parse one IFC element reference, raising a node-scoped error otherwise.

    ``node`` names the consuming node so the error says who rejected the
    reference (e.g. ``loi_check requires IFC element references ...``).
    """
    slug, kind, value = split_reference(reference)
    if kind != EXPR_KIND:
        raise ValueError(
            f"{node} requires IFC element references ('<slug>:expr:<id>'), "
            f"got '{reference}'."
        )
    return ElementRef(reference=reference, slug=slug, express_id=int(value))


def parse_element_refs(references: list[str], *, node: str) -> list[ElementRef]:
    """Parse a list of IFC element references, raising on the first bad one."""
    return [parse_element_ref(reference, node=node) for reference in references]


def iter_resolved_elements(
    references: list[str],
    context: ExecutionContext,
    *,
    node: str,
) -> Iterator[tuple[ElementRef, Any]]:
    """Yield ``(ElementRef, model)`` pairs, resolving each slug's model once.

    The shared consumer loop: parse every reference up front (raising a
    node-scoped error on the first non-element reference), then walk the list
    in order with each reference's own model memoized per slug.
    """
    models: dict[str, Any] = {}
    for element in parse_element_refs(references, node=node):
        if element.slug not in models:
            models[element.slug] = context.resolve_model(element.slug)
        yield element, models[element.slug]


def split_reference(key: str) -> tuple[str, str, int | str]:
    """Parse a qualified reference into ``(slug, kind, value)``.

    - ``<slug>:expr:<id>`` resolves to ``(slug, "expr", express_id)``.
    - ``gen:<object_id>`` resolves to ``("", "gen", object_id)``.

    Raises ``ValueError`` for anything else — bare integers, plain strings,
    ``inter:`` helper keys, guid keys. Callers that need an IFC entity should
    use :func:`parse_element_ref`, which rejects non-``expr`` kinds with a
    node-scoped error.
    """
    if not key:
        raise ValueError(f"'{key!r}' is not a valid qualified reference.")

    parsed = split_expr_key(key)
    if parsed is not None:
        slug, express_id = parsed
        return slug, EXPR_KIND, express_id

    if key.startswith(_GEN_PREFIX):
        object_id = key[len(_GEN_PREFIX) :]
        if object_id:
            return "", GEN_KIND, object_id

    raise ValueError(
        f"'{key}' is not a valid qualified reference. "
        "Expected '<slug>:expr:<id>' or 'gen:<object_id>'."
    )


def is_generated_key(key: str) -> bool:
    """True for ``gen:<object_id>`` keys (generated/external geometry)."""
    return key.startswith(_GEN_PREFIX)


def is_geometry_key(key: str) -> bool:
    """True for any valid geometry cache reference: ``expr:``, ``gen:`` or ``inter:``.

    Guid keys are identifiers, not geometry, and return ``False``.
    """
    return (
        split_expr_key(key) is not None
        or key.startswith(_GEN_PREFIX)
        or key.startswith(_INTER_PREFIX)
    )


def guid_key(slug: str, guid: str) -> str:
    """Build the qualified GUID reference ``<slug>:guid:<GUID>``.

    GlobalIds cannot contain colons, so the marker parses clean.
    """
    if not slug or not guid:
        raise ValueError("guid_key requires a non-empty slug and GUID.")
    if ":" in guid:
        raise ValueError(f"Invalid GlobalId '{guid}': GlobalIds cannot contain colons.")
    return f"{slug}:guid:{guid}"


def split_guid_key(key: str) -> tuple[str, str] | None:
    """Split a guid key ``<slug>:guid:<GUID>`` into ``(slug, guid)``.

    Returns ``None`` for keys that are not guid keys.
    """
    start = key.find(_GUID_MARKER)
    if start <= 0:
        return None
    slug = key[:start]
    guid = key[start + len(_GUID_MARKER) :]
    if not guid or ":" in guid:
        return None
    return slug, guid


__all__ = [
    "EXPR_KIND",
    "GEN_KIND",
    "GUID_KIND",
    "ElementRef",
    "expand_reference",
    "expr_key",
    "guid_key",
    "is_generated_key",
    "is_geometry_key",
    "iter_resolved_elements",
    "parse_element_ref",
    "parse_element_refs",
    "split_expr_key",
    "split_guid_key",
    "split_reference",
]
