from pydantic import BaseModel


class DeviceConfigOut(BaseModel):
    # camelCase a proposito: esta forma sustituye tal cual el objeto
    # config_maceteros que Node-RED ya lee de su contexto global, no
    # sigue la convencion snake_case del resto de la API.
    humedadMin: int
    horaInicio: int
    horaFin: int
    duracionRiegoMs: int
    lluviaPrevista: bool
