from __future__ import annotations

import os
import uuid

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..models import Organization, StatPlan
from website.utils.stat_import import find_organization_by_okpo, save_parsed_report
from website.utils.stat_parse import StatParseError, parse_stat_file

bp = Blueprint("stat_plans", __name__, url_prefix="/stat-reports")

ALLOWED_EXT = {".xlsx", ".xlsm"}

def _tmp_dir() -> str:
    path = os.path.join(current_app.instance_path, "tmp_stat_uploads")
    os.makedirs(path, exist_ok=True)
    return path


@bp.route("/", methods=["GET"])
@login_required
def list_reports():
    reports = StatPlan.query.order_by(StatPlan.uploaded_at.desc()).limit(200).all()
    return render_template("stat_plans/list.html", reports=reports)


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("stat_plans/upload.html")

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Файл не выбран", "error")
        return redirect(url_for("stat_plans.upload"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        flash("Поддерживаются только файлы .xlsx/.xlsm", "error")
        return redirect(url_for("stat_plans.upload"))

    token = uuid.uuid4().hex
    tmp_path = os.path.join(_tmp_dir(), f"{token}{ext}")
    file.save(tmp_path)

    try:
        parsed = parse_stat_file(tmp_path, file.filename)
    except StatParseError as e:
        os.remove(tmp_path)
        flash(f"Не удалось разобрать файл: {e}", "error")
        return redirect(url_for("stat_plans.upload"))

    matched_org = find_organization_by_okpo(parsed.okpo_from_filename)
    organizations = Organization.query.order_by(Organization.name).all()

    return render_template(
        "stat_plans/preview.html",
        parsed=parsed,
        token=token,
        ext=ext,
        matched_org=matched_org,
        organizations=organizations,
    )


@bp.route("/upload/confirm", methods=["POST"])
@login_required
def upload_confirm():
    token = request.form.get("token", "")
    ext = request.form.get("ext", ".xlsx")
    filename = request.form.get("filename", "")
    organization_id = request.form.get("organization_id", type=int)

    tmp_path = os.path.join(_tmp_dir(), f"{token}{ext}")

    if not organization_id:
        flash("Не выбрана организация", "error")
        return redirect(url_for("stat_plans.upload"))

    if not os.path.exists(tmp_path):
        flash("Время загрузки истекло, загрузите файл повторно", "error")
        return redirect(url_for("stat_plans.upload"))

    try:
        parsed = parse_stat_file(tmp_path, filename)
        report = save_parsed_report(
            parsed,
            organization_id,
            uploaded_by_id=current_user.id,
            replace=True,
        )
        flash(
            f"Отчёт {parsed.report_type} за {parsed.report_year} год сохранён "
            f"({len(parsed.values)} значений)",
            "success",
        )
    except StatParseError as e:
        flash(f"Не удалось разобрать файл: {e}", "error")
        return redirect(url_for("stat_plans.upload"))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return redirect(url_for("stat_plans.view_report", report_id=report.id))


@bp.route("/<int:report_id>")
@login_required
def view_report(report_id):
    report = StatPlan.query.get_or_404(report_id)
    values = sorted(
        report.values,
        key=lambda v: (v.row_code.zfill(6), v.column_code.zfill(2), v.period),
    )
    return render_template("stat_plans/view.html", report=report, values=values)


@bp.route("/<int:report_id>/delete", methods=["POST"])
@login_required
def delete_report(report_id):
    report = StatPlan.query.get_or_404(report_id)
    from . import db  # локальный импорт, чтобы не плодить циклы при загрузке пакета
    db.session.delete(report)
    db.session.commit()
    flash("Отчёт удалён", "success")
    return redirect(url_for("stat_plans.list_reports"))