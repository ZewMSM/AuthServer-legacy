import logging

import uvicorn
from fastapi import FastAPI, Request

from auth_server import game_auth
from auth_server.game_auth import create_anon_account

logger = logging.getLogger('Default')

app = FastAPI()


@app.post("/purchases/steam/my_singing_monsters/ProcessInitializedPurchases.php", tags=['STUFF'])
async def steam_purchases(request: Request):
    params = await request.form()

    return {"ok": True, "processed_order": True}


@app.post("/auth/api/anon_account/", tags=['GAME'])
async def anon_account(request: Request):
    params = await request.form()

    game_id = int(params.get("g", '-1'))
    device_model = params.get("device_model", None)
    device_vendor = params.get("device_vendor", None)
    device_id = params.get("device_id", None)
    platform = params.get("platform", None)
    os_version = params.get("os_version", None)

    if game_id in (1, 27):
        return await create_anon_account(request.client.host, 1, device_model, device_vendor, device_id, platform, os_version)
    logger.info(f'Host {request.client.host} tried to create account to undefined game!')
    return "Пошел нахуй"


@app.post("/auth/api/token", tags=['GAME'])
async def get_auth_token(request: Request):
    params = await request.form()
    logger.info(params)

    username = params.get("u", None)
    password = params.get("p", None)
    game_id = int(params.get("g", '-1'))
    login_type = params.get("t", None)

    is_refresh_token = bool(params.get("refresh_token", 1))
    device_model = params.get("device_model", None)
    device_vendor = params.get("device_vendor", None)
    device_id = params.get("device_id", None)
    platform = params.get("platform", None)
    os_version = params.get("os_version", None)

    if game_id in (1, 27):
        return await game_auth.request_auth_token(request.client.host, username, password, login_type, 1, device_vendor, device_model, os_version, device_id, platform, is_refresh_token)
    logger.info(f'User {username} tried to login to undefined game!')
    return "Пошел нахуй"


@app.post('/pregame_setup.php', tags=['GAME'])
async def get_server_info(request: Request):
    params = await request.form()
    logger.info(params)

    auth_token = request.headers.get('Authorization', None)
    access_key = params.get("access_key", None)
    client_version = params.get("client_version", None)

    return await game_auth.pregame_setup(auth_token, access_key, client_version)


@app.get('/my_singing_monsters/dlc/{version}/r{user_id}-{rev_hash}/{file_path:path}', tags=['GAME'])
async def dlc(version: str, user_id: int, rev_hash: str, file_path):
    return await game_auth.get_dlc_file(version, file_path, user_id)


async def start_auth_server():
    logger.info("Starting auth server...")
    config = uvicorn.Config(app, host="0.0.0.0", port=443, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
