"""Админ-панель: добавление организации по УНП с подстановкой данных из
ЕГР (utils/egr.py). Два шага на одной странице:
  1) ввод УНП → «Найти в ЕГР» — показ того, что вернул ЕГР (полное и
     сокращённое наименование, область по СОАТО, юр. адрес, состояние);
     если организация с таким УНП уже есть в базе — ссылка на неё;
  2) правка при необходимости, ОКПО (в ЕГР его нет), роли → «Добавить».
"""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from common_models import current_utc_time, db

from ..models import Ministry, Organization, Region

admin_org_bp = Blueprint('admin_org', __name__, url_prefix='/admin/org-by-unp')

ROLE_FIELDS = [
    ('is_regular', 'Разработчик (обычная)'),
    ('is_coordinator', 'Согласующая'),
    ('is_approver', 'Утверждающая'),
    ('is_region_management', 'Региональное управление'),
    ('is_energy_department', 'Департамент по энергоэффективности'),
]


@admin_org_bp.before_request
def _guard():
    if not current_user.is_authenticated or not current_user.is_admin:
        abort(403)


def _site_ctx():
    site = current_app.extensions.get('cm_admin')
    return site.nav_context() if site else {}


def _existing(unp):
    return Organization.query.filter(Organization.ynp == unp).first()


@admin_org_bp.route('/', methods=['GET', 'POST'])
def by_unp():
    from website.utils.egr import EgrError, fetch_organization, normalize_unp, STATUS_LABELS, INACTIVE_KINDS

    regions = Region.query.order_by(Region.number).all()
    ministries = Ministry.query.order_by(Ministry.name).all()
    ctx = dict(regions=regions, ministries=ministries, role_fields=ROLE_FIELDS,
               status_labels=STATUS_LABELS, inactive_kinds=INACTIVE_KINDS,
               unp=(request.values.get('unp') or '').strip(), egr=None, existing=None,
               form=request.form, error=None)

    action = request.form.get('action')

    if request.method == 'POST' and action == 'lookup':
        try:
            unp = normalize_unp(ctx['unp'])
            ctx['unp'] = unp
            ctx['existing'] = _existing(unp)
            if not ctx['existing']:
                egr = fetch_organization(unp)
                if egr.get('region_number'):
                    region = Region.query.filter_by(number=egr['region_number']).first()
                    egr['region_id'] = region.id if region else None
                ctx['egr'] = egr
        except EgrError as exc:
            ctx['error'] = str(exc)

    elif request.method == 'POST' and action == 'create':
        try:
            unp = normalize_unp(ctx['unp'])
        except EgrError as exc:
            ctx['error'] = str(exc)
            return render_template('admin/org_by_unp.html', **ctx, **_site_ctx())

        existing = _existing(unp)
        if existing:
            flash(f'Организация с УНП {unp} уже есть в базе', 'error')
            return redirect(url_for('cm_admin.edit_view', key='organization', pk=existing.id))

        full_name = (request.form.get('full_name') or '').strip()
        okpo = (request.form.get('okpo') or '').strip() or None
        if not full_name:
            ctx['error'] = 'Укажите полное наименование'
        elif okpo and Organization.query.filter_by(okpo=okpo).first():
            ctx['error'] = f'Организация с ОКПО {okpo} уже есть в базе'
        if ctx['error']:
            ctx['egr'] = {k: request.form.get(k) for k in ('full_name', 'short_name', 'legal_address', 'status', 'status_kind')}
            ctx['egr']['region_id'] = request.form.get('region_id', type=int)
            return render_template('admin/org_by_unp.html', **ctx, **_site_ctx())

        org = Organization(
            full_name=full_name,
            short_name=(request.form.get('short_name') or '').strip() or None,
            ynp=unp,
            okpo=okpo,
            region_id=request.form.get('region_id', type=int) or None,
            ministry_id=request.form.get('ministry_id', type=int) or None,
            legal_address=(request.form.get('legal_address') or '').strip() or None,
            egr_status=(request.form.get('status') or '').strip() or None,
            egr_status_kind=(request.form.get('status_kind') or '').strip() or None,
            egr_checked_at=current_utc_time(),
            is_active=True,
            **{name: bool(request.form.get(name)) for name, _ in ROLE_FIELDS},
        )
        db.session.add(org)
        db.session.commit()
        current_app.logger.info(f'Admin {current_user.id} added organization {org.id} by UNP {unp} from EGR')
        flash(f'Организация «{org.full_name}» добавлена', 'success')
        return redirect(url_for('cm_admin.edit_view', key='organization', pk=org.id))

    return render_template('admin/org_by_unp.html', **ctx, **_site_ctx())
