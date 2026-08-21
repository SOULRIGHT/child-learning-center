"""면제권 JSON 복원. ChildReading 복원 이후에 호출한다."""
from __future__ import annotations

from datetime import date, datetime

from extensions import db
from feature_models import ExemptionTicket, ExemptionTicketSource, ExemptionUsage


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def restore_exemptions_from_backup_data(backup_data):
    """ExemptionTicket → ExemptionTicketSource → ExemptionUsage 순서."""
    tickets = (backup_data or {}).get('exemption_tickets') or []
    restored_tickets = 0
    for item in tickets:
        if not isinstance(item, dict):
            continue
        child_id = item.get('child_id')
        issued_on = _parse_date(item.get('issued_on'))
        expires_on = _parse_date(item.get('expires_on'))
        if not child_id or issued_on is None or expires_on is None:
            continue
        ticket_id = item.get('id')
        ticket = ExemptionTicket.query.get(ticket_id) if ticket_id else None
        if ticket is None:
            ticket = ExemptionTicket(id=ticket_id) if ticket_id else ExemptionTicket()
            db.session.add(ticket)
        ticket.child_id = child_id
        ticket.issued_on = issued_on
        ticket.expires_on = expires_on
        ticket.status = item.get('status') or 'active'
        ticket.policy_version = item.get('policy_version') or 'v1'
        ticket.issued_by_user_id = item.get('issued_by_user_id')
        ticket.revoked_at = _parse_dt(item.get('revoked_at'))
        ticket.revoked_by_user_id = item.get('revoked_by_user_id')
        created_at = _parse_dt(item.get('created_at'))
        if created_at:
            ticket.created_at = created_at
        restored_tickets += 1

    db.session.flush()

    sources = (backup_data or {}).get('exemption_ticket_sources') or []
    restored_sources = 0
    for item in sources:
        if not isinstance(item, dict):
            continue
        ticket_id = item.get('exemption_ticket_id')
        reading_id = item.get('child_reading_id')
        if not ticket_id or not reading_id:
            continue
        source_id = item.get('id')
        source = ExemptionTicketSource.query.get(source_id) if source_id else None
        if source is None:
            source = (
                ExemptionTicketSource.query.filter_by(
                    exemption_ticket_id=ticket_id,
                    child_reading_id=reading_id,
                ).first()
            )
        if source is None:
            source = ExemptionTicketSource(id=source_id) if source_id else ExemptionTicketSource()
            db.session.add(source)
        source.exemption_ticket_id = ticket_id
        source.child_reading_id = reading_id
        created_at = _parse_dt(item.get('created_at'))
        if created_at:
            source.created_at = created_at
        restored_sources += 1

    db.session.flush()

    usages = (backup_data or {}).get('exemption_usages') or []
    restored_usages = 0
    for item in usages:
        if not isinstance(item, dict):
            continue
        ticket_id = item.get('exemption_ticket_id')
        subject_key = (item.get('subject_key') or '').strip().lower()
        subject_name = (item.get('subject_name') or '').strip()
        used_on = _parse_date(item.get('used_on'))
        if not ticket_id or not subject_key or not subject_name or used_on is None:
            continue
        usage_id = item.get('id')
        usage = ExemptionUsage.query.get(usage_id) if usage_id else None
        if usage is None:
            usage = ExemptionUsage.query.filter_by(exemption_ticket_id=ticket_id).first()
        if usage is None:
            usage = ExemptionUsage(id=usage_id) if usage_id else ExemptionUsage()
            db.session.add(usage)
        usage.exemption_ticket_id = ticket_id
        usage.subject_key = subject_key
        usage.subject_name = subject_name
        usage.used_on = used_on
        usage.recorded_by_user_id = item.get('recorded_by_user_id')
        created_at = _parse_dt(item.get('created_at'))
        if created_at:
            usage.created_at = created_at
        restored_usages += 1

    db.session.commit()
    return restored_tickets, restored_sources, restored_usages
