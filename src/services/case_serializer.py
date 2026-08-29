"""CASE API output serialization: compat vs strict.

Two output modes, decided in one place:

- **compat** (default): what compeito has always emitted — single resources
  wrapped OpenSALT-style, optional fields echoed as ``null``, package-context
  URIs included. Existing clients and the static-publish snapshots depend on it.
- **strict** (``?strict=1``): the shape the official CASE v1.1 OpenAPI schema
  describes — flat single resources, no ``null`` for optional fields (no DType
  declares one nullable), no package-context URIs (``additionalProperties:
  false``), and ``caseVersion`` declared as the version this server speaks.

Design: docs/dev/designs/strict-output.md (conformance backlog C16 / C1 / C2 /
C8, N7). Flipping the default to strict is a later, separate step — it should be
a one-line change to ``settings.case_output_default``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from src.config import settings
from src.errors import OutputModeConflictError
from src.schemas.cf_document import CFDocumentDType, CFPckgDocumentDType
from src.schemas.cf_package import CFPackageDType
from src.schemas.common import CASEBaseSchema

OutputMode = Literal["compat", "strict"]

TRUTHY = {"1", "true", "yes", "on"}

# What a CASE v1.1 server declares in strict mode. Not fabricated source data:
# it states which version's shape this response has, and compeito serves v1.1
# even for documents imported from a v1.0 source.
CASE_VERSION_EMIT = "1.1"


def _is_truthy(value: str | None) -> bool:
    # Surrounding whitespace is tolerated (`?strict=%201%20`): it can only come
    # from a hand-built URL, and the intent is unambiguous.
    return value is not None and value.strip().lower() in TRUTHY


def resolve_output_mode(strict: str | None, compat: str | None) -> OutputMode:
    """Decide the output mode from the two query parameters.

    A non-truthy value (``?strict=0``, ``?strict=abc``) counts as "not asked
    for", so a typo falls back to the default rather than silently selecting the
    other mode. Asking for both at once is a contradiction, not a precedence
    puzzle — it errors instead of guessing.
    """
    want_strict = _is_truthy(strict)
    want_compat = _is_truthy(compat)
    if want_strict and want_compat:
        raise OutputModeConflictError("Cannot request both strict and compat output; specify at most one")
    if want_strict:
        return "strict"
    if want_compat:
        return "compat"
    return settings.case_output_default


def dump_model(model: CASEBaseSchema, mode: OutputMode) -> dict:
    """Serialize one resource (C16 + C8).

    ``exclude_none`` is what makes strict output schema-valid: no DType in the
    official schema is nullable, so every echoed ``null`` is a type violation.
    Note it only drops fields whose *value* is None — the contents of
    ``extensions`` are user data and stay untouched in both modes.
    """
    strict = mode == "strict"
    dumped = model.model_dump(by_alias=True, exclude_none=strict)
    if strict and isinstance(model, (CFDocumentDType, CFPckgDocumentDType)):
        dumped["caseVersion"] = CASE_VERSION_EMIT
    return dumped


def dump_single(model: CASEBaseSchema, mode: OutputMode, *, compat_wrapper: str) -> dict:
    """Single-resource response (C1).

    The official binding returns the DType at the root; compeito's historical
    wrapper (``{"CFDocument": {...}}``) is OpenSALT's shape. Only the six
    single-resource routes lose their wrapper in strict mode — the Set types
    (CFItemTypes / CFConcepts / CFSubjects) and CFItemAssociations are wrapped
    in the official schema too, so theirs stay in both modes.
    """
    dumped = dump_model(model, mode)
    return dumped if mode == "strict" else {compat_wrapper: dumped}


def dump_collection(models: Sequence[CASEBaseSchema], mode: OutputMode, *, wrapper: str) -> dict:
    """List / Set response. The wrapper is kept in both modes (see dump_single)."""
    return {wrapper: [dump_model(m, mode) for m in models]}


def dump_package(package: CFPackageDType, mode: OutputMode) -> dict:
    """CFPackage response — flat in both modes (that is already the official shape).

    Strict additionally drops the package-context URIs: ``CFPckgDocumentDType``
    and ``CFPckgItemDType`` are ``additionalProperties: false`` and do not
    declare them. compeito echoes them by default because OpenCASE and OpenSALT
    do, which keeps a round trip through those tools lossless.
    """
    strict = mode == "strict"
    content = package.model_dump(by_alias=True, exclude_none=strict)
    if strict:
        document = content.get("CFDocument")
        if isinstance(document, dict):
            document.pop("CFPackageURI", None)
            document["caseVersion"] = CASE_VERSION_EMIT
        for item in content.get("CFItems", []):
            item.pop("CFDocumentURI", None)
    return content
