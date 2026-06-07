"""Unit tests for the XLSX import/export services (OpenSALT Excel format).

The core check is a round-trip: build a framework via the custom CSV importer,
export it to an OpenSALT-format .xlsx, re-import that workbook into a fresh
document, and assert the items / hierarchy / item types / education levels and
the non-isChildOf associations survive.
"""

from __future__ import annotations

import io
import uuid

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.models.cf_association import CFAssociation
from src.models.cf_item import CFItem
from src.models.tenant import Tenant
from src.services.csv_import_service import import_csv
from src.services.xlsx_export_service import export_xlsx
from src.services.xlsx_import_service import import_xlsx

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

# A small custom-format framework: 2 roots, one with a child; item types and
# education levels set; plus one non-isChildOf (isRelatedTo) association.
SOURCE_CSV = (
    "#identifier,dddddddd-0000-0000-0000-000000000001\n"
    "#title,XLSX Source Framework\n"
    "#creator,Test Author\n"
    "#language,ja\n"
    "#version,1.0\n"
    "#subject,情報科学,データ\n"
    "Identifier,fullStatement,humanCodingScheme,parentIdentifier,sequenceNumber,CFItemType,educationLevel,conceptKeywords,abbreviatedStatement,language,listEnumeration,license,statusStartDate,statusEndDate\n"  # noqa: E501
    "10000000-0000-0000-0000-000000000001,Root A,A,,10,領域,13,,Root A short,,,,,\n"
    '10000000-0000-0000-0000-000000000002,Child A1,A-1,10000000-0000-0000-0000-000000000001,10,知識,"13,14","kw1,kw2",Child A1 short,,,,,\n'  # noqa: E501
    "10000000-0000-0000-0000-000000000003,Root B,B,,20,領域,14,,Root B short,,,,,\n"
)


async def _seed_source(session: AsyncSession) -> uuid.UUID:
    session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
    await session.flush()
    report = await import_csv(session, TENANT_ID, SOURCE_CSV.encode("utf-8"))
    await session.flush()
    # Add a non-isChildOf association: Child A1 isRelatedTo Root B.
    doc_id = uuid.UUID(report.document_identifier)
    from src.models.cf_document import CFDocument

    doc = (await session.execute(select(CFDocument).where(CFDocument.identifier == doc_id))).scalar_one()
    a1 = uuid.UUID("10000000-0000-0000-0000-000000000002")
    b = uuid.UUID("10000000-0000-0000-0000-000000000003")
    session.add(
        CFAssociation(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            cf_document_id=doc.id,
            identifier=uuid.UUID("20000000-0000-0000-0000-0000000000aa"),
            uri="https://example.com/assoc/aa",
            association_type="isRelatedTo",
            origin_node_uri=f"https://example.com/{a1}",
            origin_node_identifier=str(a1),
            destination_node_uri=f"https://example.com/{b}",
            destination_node_identifier=str(b),
            last_change_date_time=doc.last_change_date_time,
        )
    )
    await session.flush()
    return doc_id


class TestXlsxExport:
    async def test_export_workbook_structure(self, db_session: AsyncSession):
        doc_id = await _seed_source(db_session)
        data = await export_xlsx(db_session, TENANT_ID, doc_id)

        wb = load_workbook(io.BytesIO(data))
        assert wb.sheetnames == ["CF Doc", "CF Item", "CF Association"]

        # CF Doc: header + 1 data row
        doc_ws = wb["CF Doc"]
        assert doc_ws.cell(1, 1).value == "identifier"
        assert doc_ws.cell(2, 3).value == "XLSX Source Framework"  # title col C
        assert doc_ws.cell(2, 8).value == "情報科学|データ"  # subject pipe-joined

        # CF Item: 3 data rows with smartLevel
        item_ws = wb["CF Item"]
        rows = list(item_ws.iter_rows(min_row=2, values_only=True))
        by_stmt = {r[1]: r for r in rows}
        assert by_stmt["Root A"][3] == "1"  # smartLevel col D
        assert by_stmt["Child A1"][3] == "1.1"
        assert by_stmt["Root B"][3] == "2"
        assert by_stmt["Child A1"][10] == "知識"  # CFItemType col K
        assert by_stmt["Child A1"][9] == "13,14"  # educationLevel col J

        # CF Association: the isRelatedTo (isChildOf NOT repeated here)
        assoc_ws = wb["CF Association"]
        arows = list(assoc_ws.iter_rows(min_row=2, values_only=True))
        assert len(arows) == 1
        assert arows[0][4] == "isRelatedTo"  # associationType col E

    async def test_export_doc_not_found(self, db_session: AsyncSession):
        db_session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
        await db_session.flush()
        with pytest.raises(ValueError):
            await export_xlsx(db_session, TENANT_ID, uuid.uuid4())


class TestXlsxRoundTrip:
    async def test_roundtrip_into_new_document(self, db_session: AsyncSession):
        src_doc = await _seed_source(db_session)
        data = await export_xlsx(db_session, TENANT_ID, src_doc)

        # Re-import the workbook (same identifiers → upsert in place).
        report = await import_xlsx(db_session, TENANT_ID, data)
        await db_session.flush()
        assert report.document_identifier == str(src_doc)

        from src.models.cf_document import CFDocument

        doc = (await db_session.execute(select(CFDocument).where(CFDocument.identifier == src_doc))).scalar_one()

        items = list(
            (
                await db_session.execute(
                    select(CFItem).options(joinedload(CFItem.item_type)).where(CFItem.cf_document_id == doc.id)
                )
            )
            .scalars()
            .unique()
        )
        assert len(items) == 3
        by_stmt = {i.full_statement: i for i in items}
        # Item type + education level survived the round-trip.
        child = by_stmt["Child A1"]
        assert child.item_type is not None and child.item_type.title == "知識"
        assert child.education_level == ["13", "14"]

        # isChildOf rebuilt from smartLevel: Child A1 → Root A.
        ischild = list(
            (
                await db_session.execute(
                    select(CFAssociation).where(
                        CFAssociation.cf_document_id == doc.id,
                        CFAssociation.association_type == "isChildOf",
                    )
                )
            ).scalars()
        )
        root_a = by_stmt["Root A"]
        child_links = [a for a in ischild if a.origin_node_identifier == str(child.identifier)]
        assert len(child_links) == 1
        assert child_links[0].destination_node_identifier == str(root_a.identifier)

        # Non-isChildOf association preserved.
        related = list(
            (
                await db_session.execute(
                    select(CFAssociation).where(
                        CFAssociation.cf_document_id == doc.id,
                        CFAssociation.association_type == "isRelatedTo",
                    )
                )
            ).scalars()
        )
        assert len(related) == 1


class TestXlsxAssociationGrouping:
    async def test_import_association_with_grouping(self, db_session: AsyncSession):
        """A CF Association row carrying an associationGroupIdentifier must
        find-or-create a (tenant-wide) CFAssociationGrouping — regression guard
        for the document-scoped lookup bug."""
        from openpyxl import Workbook

        from src.models.cf_association_grouping import CFAssociationGrouping

        db_session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
        await db_session.flush()

        origin = uuid.UUID("30000000-0000-0000-0000-000000000001")
        dest = uuid.UUID("30000000-0000-0000-0000-000000000002")
        group = uuid.UUID("40000000-0000-0000-0000-0000000000aa")

        wb = Workbook()
        wb.remove(wb.active)
        d = wb.create_sheet("CF Doc")
        d.append(["identifier", "creator", "title"] + [""] * 13)
        d.append([str(uuid.uuid4()), "A", "Grouping Test"] + [""] * 13)
        it = wb.create_sheet("CF Item")
        it.append(["identifier", "fullStatement", "humanCodingScheme", "smartLevel"] + [""] * 8)
        it.append([str(origin), "Origin item", "O", "1"] + [""] * 8)
        it.append([str(dest), "Dest item", "D", "2"] + [""] * 8)
        a = wb.create_sheet("CF Association")
        a.append(
            [
                "identifier",
                "originNodeURI",
                "originNodeIdentifier",
                "originNodeHumanCodingScheme",
                "associationType",
                "destinationNodeURI",
                "destinationNodeIdentifier",
                "destinationNodeHumanCodingScheme",
                "associationGroupIdentifier",
                "associationGroupName",
            ]
        )
        a.append(
            [
                str(uuid.uuid4()),
                "",
                str(origin),
                "",
                "isRelatedTo",
                "",
                str(dest),
                "",
                str(group),
                "Crosswalk Group",
            ]
        )
        buf = io.BytesIO()
        wb.save(buf)

        await import_xlsx(db_session, TENANT_ID, buf.getvalue())
        await db_session.flush()

        groupings = list(
            (
                await db_session.execute(
                    select(CFAssociationGrouping).where(CFAssociationGrouping.tenant_id == TENANT_ID)
                )
            ).scalars()
        )
        assert len(groupings) == 1
        assert groupings[0].identifier == group
        assert groupings[0].title == "Crosswalk Group"

        rel = (
            await db_session.execute(select(CFAssociation).where(CFAssociation.association_type == "isRelatedTo"))
        ).scalar_one()
        assert rel.cf_association_grouping_id == groupings[0].id


class TestXlsxImportErrors:
    async def test_non_xlsx_bytes(self, db_session: AsyncSession):
        db_session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
        await db_session.flush()
        with pytest.raises(ValueError):
            await import_xlsx(db_session, TENANT_ID, b"not an xlsx file")

    async def test_missing_required_sheet(self, db_session: AsyncSession):
        db_session.add(Tenant(id=TENANT_ID, name="T", is_private=False))
        await db_session.flush()
        from openpyxl import Workbook

        wb = Workbook()
        wb.active.title = "CF Doc"  # missing CF Item
        buf = io.BytesIO()
        wb.save(buf)
        with pytest.raises(ValueError, match="CF Item"):
            await import_xlsx(db_session, TENANT_ID, buf.getvalue())
