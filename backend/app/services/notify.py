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
            # body puede traer el marcador "{device_name}" - se sustituye
            # aqui, no en cada llamador, porque solo aqui se tiene ya
            # cargado el nombre amigable del dispositivo (o su device_id
            # como respaldo si no tiene nombre puesto, mismo criterio que
            # el resto de la app: device.name ?? device_id).
            display_name = device.name or device.device_id
            send_push_notification(owner.push_token, title, body.format(device_name=display_name))
    finally:
        db.close()
