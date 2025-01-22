import json
import uuid

from cassandra.cluster import Cluster
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from os import getenv

SCYLLADB_URL = getenv("SCYLLADB_URL", "127.0.0.1")

print(SCYLLADB_URL)

app = FastAPI()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: object):
        for connection in self.active_connections:
            await connection.send_json(data)


manager = ConnectionManager()


class User(BaseModel):
    id: uuid.UUID | str | None = None
    name: str | None = None

    def tojson(self):
        self.id = str(self.id)

        return json.dumps(
            self,
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent=4)


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/api/getAll")
def read_item():
    response = {
        "message": "ok",
        "error": False,
        "data": None
    }

    data = None

    try:
        cluster = Cluster(contact_points=[SCYLLADB_URL])
        session = cluster.connect("local")
        rows = session.execute('SELECT id, name FROM users')
        data = list()

        for row in rows:
            data.append({
                "id": row.id,
                "name": row.name
            })
    except Exception as error:
        print(error)

        response["message"] = str(error)
        response["error"] = True

    response["data"] = data

    return response


@app.post("/api/insert")
async def read_item(body: User):
    response = {
        "message": "ok",
        "error": False,
        "data": None
    }

    try:
        body.id = uuid.uuid4()

        cluster = Cluster(contact_points=[SCYLLADB_URL])
        session = cluster.connect("local")
        session.execute(
            "INSERT INTO users (id, name) VALUES (%s, %s)",
            [
                body.id,
                body.name
            ]
        )

    except Exception as error:
        print(error)

        response["message"] = str(error)
        response["error"] = True

    response["data"] = body
    await manager.broadcast({
        "action": "addUser",
        "data": body.tojson()
    })

    return response


@app.post("/api/delete")
async def read_item(body: User):
    response = {
        "message": "ok",
        "error": False,
        "data": None
    }

    try:
        cluster = Cluster(contact_points=[SCYLLADB_URL])
        session = cluster.connect("local")
        session.execute(
            "DELETE FROM users WHERE id = %s",
            [
                uuid.UUID(body.id)
            ]
        )

    except Exception as error:
        print(error)

        response["message"] = str(error)
        response["error"] = True

    response["data"] = body
    await manager.broadcast({
        "action": "deleteUser",
        "data": body.tojson()
    })

    return response


@app.post("/api/update")
async def read_item(body: User):
    response = {
        "message": "ok",
        "error": False,
        "data": None
    }

    try:
        cluster = Cluster(contact_points=[SCYLLADB_URL])
        session = cluster.connect("local")
        rows = session.execute('SELECT id, name FROM users WHERE id = %s', [
            uuid.UUID(body.id)
        ])
        if len(list(rows)) < 1:
            raise Exception("User not found")

        session.execute(
            "UPDATE users SET name = %s WHERE id = %s",
            [
                body.name,
                uuid.UUID(body.id)
            ]
        )

    except Exception as error:
        print(error)

        response["message"] = str(error)
        response["error"] = True

    response["data"] = body
    await manager.broadcast({
        "action": "updateUser",
        "data": body.tojson()
    })

    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


app.mount("/static", StaticFiles(directory="static"), name="static")
