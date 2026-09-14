from __future__ import annotations

import io
import zipfile
from typing import Optional, Tuple

from website.models import Organization, StatPlan, StatPlanValue
from website.utils.stat_parse import ParsedStatPlan, parse_stat_file


class OrganizationNotFoundError(Exception):
    def __init__(self, okpo: Optional[str]):
        self.okpo = okpo
        msg = (
            f'Организация с ОКПО "{okpo}" не найдена в справочнике'
            if okpo else
            "Не удалось определить ОКПО по имени файла — выберите организацию вручную"
        )
        super().__init__(msg)


def find_organization_by_okpo(okpo: Optional[str]) -> Optional[Organization]:
    if not okpo:
        return None
    return Organization.query.filter_by(okpo=str(okpo)).first()


def save_parsed_report(
    parsed: ParsedStatPlan,
    organization_id: int,
    db,
    uploaded_by_id: Optional[int] = None,
    replace: bool = True,
) -> StatPlan:
    existing = StatPlan.query.filter_by(
        organization_id=organization_id,
        type=parsed.type,
        year=parsed.year,
    ).first()

    if existing:
        if not replace:
            raise ValueError(
                f"Отчёт {parsed.type} за {parsed.year} год "
                f"для этой организации уже загружен (id={existing.id})"
            )
        StatPlanValue.query.filter_by(stat_plan_id=existing.id).delete()
        db.session.flush()
        report = existing
        if uploaded_by_id is not None:
            report.uploaded_by_id = uploaded_by_id
    else:
        report = StatPlan(
            organization_id=organization_id,
            type=parsed.type,
            year=parsed.year,
            uploaded_by_id=uploaded_by_id,
        )
        db.session.add(report)
        db.session.flush()

    for cv in parsed.values:
        db.session.add(
            StatPlanValue(
                stat_plan_id=report.id,
                row_code=cv.row_code,
                row_name=cv.row_name,
                column_code=cv.column_code,
                value=cv.value,
            )
        )

    db.session.commit()
    return report


def import_stat_file(
    file_path: str,
    filename: str,
    db,
    organization_id: Optional[int] = None,
    uploaded_by_id: Optional[int] = None,
    replace: bool = True,
) -> Tuple[StatPlan, ParsedStatPlan]:
    parsed = parse_stat_file(file_path, filename)

    if organization_id is None:
        org = find_organization_by_okpo(parsed.okpo_from_filename)
        if org is None:
            raise OrganizationNotFoundError(parsed.okpo_from_filename)
        organization_id = org.id

    report = save_parsed_report(parsed, organization_id, db, uploaded_by_id, replace=replace)
    return report, parsed


_JUNK_PREFIXES = ("__MACOSX/", ".")
_STAT_EXTENSIONS = (".xlsx", ".xls")


def import_stat_archive(
    fileobj,
    db,
    uploaded_by_id: Optional[int] = None,
    replace: bool = True,
) -> dict:
    """Import every ``.xlsx``/``.xls`` entry of a ZIP archive as a statistics
    report. Each entry must follow the strict naming convention parsed by
    :func:`~website.utils.stat_parse.extract_okpo_from_filename` /
    :func:`~website.utils.stat_parse.extract_year_from_filename`
    (``<окпо>_..._<год>_....xlsx``) — the report type (4-ТЭК / 12-ТЭК) itself
    is detected from the sheet contents, not the file name.

    A bad entry is recorded in ``errors`` and does not stop the rest of the
    archive from being imported. Returns::

        {"imported": [...], "skipped": [...], "errors": [...]}

    where each list holds human-readable strings for the admin UI.
    """
    try:
        zf = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile:
        raise ValueError("Файл не является корректным ZIP-архивом")

    imported, skipped, errors = [], [], []

    with zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        if not entries:
            raise ValueError("Архив пуст")

        for info in entries:
            base = info.filename.rsplit("/", 1)[-1]

            if not base or base.startswith(_JUNK_PREFIXES) or info.filename.startswith(_JUNK_PREFIXES) \
                    or base.startswith("~$"):
                continue
            if not base.lower().endswith(_STAT_EXTENSIONS):
                skipped.append(base)
                continue

            try:
                data = zf.read(info)
                parsed = parse_stat_file(io.BytesIO(data), base)

                org = find_organization_by_okpo(parsed.okpo_from_filename)
                if org is None:
                    raise OrganizationNotFoundError(parsed.okpo_from_filename)

                save_parsed_report(
                    parsed=parsed,
                    organization_id=org.id,
                    db=db,
                    uploaded_by_id=uploaded_by_id,
                    replace=replace,
                )
                imported.append(f"{base} -> {org.full_name} ({parsed.type}, {parsed.year})")
            except Exception as e:  # noqa: BLE001 — one bad file must not abort the rest
                db.session.rollback()
                errors.append(f"{base}: {e}")

    return {"imported": imported, "skipped": skipped, "errors": errors}