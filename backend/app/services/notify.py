def notify_owner(device_id: str, title: str, body: str) -> None:
    # Import diferido para evitar un ciclo de imports (database/models
    # no necesitan saber nada de este modulo).
    from app.database import SessionLocal
    from app.models.device import Device
    from app.services.push import send_push_notification

    db = SessionLocal()
    try:
        device = db.get(Device, device_id)
        if device is None or device.location is None:
            return
        owner = device.location.owner
        if owner.push_token:
            send_push_notification(owner.push_token, title, body)
    finally:
        db.close()
