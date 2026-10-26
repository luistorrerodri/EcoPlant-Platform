def notify_owner(device_id: str, title: str, body: str) -> None:
    # Import diferido para evitar un ciclo de imports (database/models
    # no necesitan saber nada de este modulo).
    from app.database import SessionLocal
    from app.models.device import Device
    from app.models.push_token import PushToken
    from app.services.push import send_push_notification

    db = SessionLocal()
    try:
        device = db.get(Device, device_id)
        if device is None or device.location is None:
            return
        owner = device.location.owner
        # title y body pueden traer el marcador "{device_name}" - se
        # sustituye aqui, no en cada llamador, porque solo aqui se tiene
        # ya cargado el nombre amigable del dispositivo (o su device_id
        # como respaldo si no tiene nombre puesto, mismo criterio que el
        # resto de la app: device.name ?? device_id). replace() y no
        # format(): un texto con llaves sueltas no debe poder romper el aviso.
        display_name = device.name or device.device_id
        title = title.replace("{device_name}", display_name)
        body = body.replace("{device_name}", display_name)

        # A todos los moviles de la cuenta (la misma cuenta se comparte
        # entre varias personas). Los tokens que Expo da por muertos se
        # borran aqui mismo.
        dead: list[PushToken] = []
        for push_token in list(owner.push_tokens):
            if not send_push_notification(push_token.token, title, body):
                dead.append(push_token)
        if dead:
            for push_token in dead:
                db.delete(push_token)
            db.commit()
    finally:
        db.close()
