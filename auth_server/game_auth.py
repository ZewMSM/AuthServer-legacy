import hashlib
import json
import logging
import os
import time
from datetime import datetime

from starlette.config import environ

from config import GameConfig
from database.user import User
from utils import md5, get_country_by_ip, aes_encrypt, uncache_login_data, cache_login_data, aes_decrypt, valid_email, get_all_files_in_dir
from fastapi.responses import FileResponse

logger = logging.getLogger('GameAuth')


class AuthResponse:
    AUTH_ERROR_USERNAME_REREGISTER = -1
    AUTH_ERROR_USERNAME = 1
    AUTH_ERROR_PASSWORD = 2
    AUTH_ERROR_INVALID_TYPE = 3
    AUTH_ERROR_MISSING_DATA = 4
    AUTH_ERROR_LOGIN_FAILED = 5
    ERROR_BAD_USERNAME_MATCH = 6
    ERROR_BAD_PASSWORD_MATCH = 7
    ERROR_LOGIN_ALREADY_EXISTS = 8
    ERROR_BAD_EMAIL_ADDRESS = 9
    AUTH_ACCOUNT_UNVERIFIED = 10
    ERROR_GAME_SERVER_NOT_FOUND = 11
    EMAIL_ADDRESS_NOT_FOUND = 12
    CONNECTION_ERROR = 13
    SERVER_MESSAGE = 14
    BIND_ERROR_LOGIN_ALREADY_BOUND = 15
    BIND_ERROR_TYPE_ALREADY_BOUND = 16
    AUTH_ERROR_FACEBOOK_AUTH_FAILED = 17
    FRIEND_ALREADY_EXISTS = 18
    FRIEND_ACCOUNT_NOT_FOUND = 19
    GENERAL_ERROR = 20
    CLIENT_MIN_VERSION_ERROR = 21
    ERROR_EMAIL_BOUNCE = 22
    ERROR_EMAIL_MAX_FAILS = 23
    AUTH_ERROR_GAMECENTER_AUTH_FAILED = 24
    BIND_ERROR_GAME_CONFLICT = 25
    AUTH_ERROR_GOOGLEPLAY_AUTH_FAILED = 26
    AUTH_ERROR_AMAZON_AUTH_FAILED = 27
    ERROR_NO_GAME_DATA_FOR_ACCOUNT = 28
    AUTH_TOKEN_MISSING = 29
    AUTH_TOKEN_PERMISSIONS = 30
    AUTH_INVALID_CLIENT_TOKEN = 31
    AUTH_INVALID_SERVER_TOKEN = 32
    GA_REWARD_NOT_FOUND = 33
    AUTH_TOO_MANY_ACCOUNTS = 34
    AUTH_GAME_CONFIG_NOT_FOUND = 35
    AUTH_GDPR_CONSENT_REQUIRED = 36
    AUTH_TOKEN_EXPIRED = 37
    AUTH_ERROR_APPLE_AUTH_FAILED = 38
    AUTH_ERROR_REFRESH_TOKEN_AUTH_FAILED = 39
    AUTH_ERROR_CREDENTIALS_EXPIRED = 40
    AUTH_ERROR_STEAM_AUTH_FAILED = 41
    AUTH_ERROR_TYPE_DISABLED = 42

    messages = [
        'Username does not exist - re-register',
        'Username does not exist',
        'Invalid password',
        'Invalid account type',
        'Required argument missing',
        'Login failed',
        'Usernames do not match',
        'Passwords do not match',
        'The username is already in use',
        'The email address is invalid',
        'The email address has not been verified',
        'Could not find the game server id based on the hostname provided',
        'Email address not found',
        'Connection error',
        'Exceeded Maximum Accounts. Too Many Accounts Created.',
        'Login info is already bound to another account',
        'A login of this type is already bound to this account',
        'Facebook failed to validate user on the server',
        'These users are already friends.',
        'No account found for that friend code.',
        "An error has occured",
        "The min client version is too low to play this game.",
        "The email address you provided probably has a typo and cannot receive mail. Please contact support to resolve this issue.",
        "Your device has been banned from sending emails. Please contact support to resolve this issue.",
        "Accounts contain same game id.",
        "Google Play authorization failed.",
        "Amazon authorization failed.",
        "Account has no data for this game.",
        "No token was present when required",
        "Invalid permissions",
        "Expected client token, server token used",
        "Expected server token, client token used",
        "Game center authorization failed.",
        "Global Achievement reward not found.",
        "Too many accounts have been created from your IP address.",
        "Game config not found for: ",
        "GDPR consent required",
        "Token Expired",
        "Apple authorization failed.",
        "Refresh Token authorization failed.",
        "Credentials are expired.",
        "Steam authorization failed.",
        "Selected account type disabled."
    ]

    @staticmethod
    def get_message(error_id):
        if error_id == -1:
            error_id = 0
        return AuthResponse.messages[error_id]

    @staticmethod
    def send_error(error_id):
        r = {"ok": False, "error": error_id, "message": AuthResponse.get_message(error_id)}
        print(r)
        return r

    @staticmethod
    def send_ok(data):
        r = {'ok': True} | data
        print(r)
        return r

    @staticmethod
    def send_message(message):
        return {"ok": False, "error": 14, "message": message}


def encrypt_token(username: str, user_game_id: str, login_type, account_id, game_id, **kwargs):
    json_data = json.dumps({"account_id": account_id, "user_game_ids": [user_game_id], "game": f'{game_id}', "token_version": 1, "generated_on": round(time.time()),
                            "expires_at": round(time.time() + 60 * 15), "username": username.strip(), "login_type": login_type} | kwargs)
    encrypted_data = aes_encrypt(json_data, environ.get("TOKEN_IV"), environ.get("TOKEN_KEY"))
    return encrypted_data


def decrypt_token(encrypted_token):
    if encrypted_token:
        try:
            decrypted_data = aes_decrypt(encrypted_token.encode("UTF-8"), environ.get("TOKEN_IV"), environ.get("TOKEN_KEY"))
            return json.loads(decrypted_data)
        except Exception as e:
            print(e)
            return None
    else:
        return None


def generate_content_url(version, user: User):
    return f"http://{environ.get('DLC_DOMAIN') if 'localhost' not in user.rights else '127.0.0.1'}/my_singing_monsters/dlc/{version}/r{user.id}-TEST/files.json"


async def refresh_token(username, password, login_type, game_id, vendor, model, os, devid, platform, ip_addr, is_refresh_token):
    cached_login_data = await uncache_login_data(game_id, username, password, login_type)

    if time.time() > cached_login_data.get('expires_at', 0) or is_refresh_token:
        user = await User.load_by_game_and_username(username, game_id)
        if user is None:
            if login_type == 'anon':
                user = User()
                user.game_id = game_id
                user.login_type = 'anon'
                user.created_from_ip = ip_addr
                user.created_from_device = devid

                user.username = username
                user.password = md5(password)
                user.date_created = round(datetime.now().timestamp())
                await user.save()
            else:
                return False, AuthResponse.send_error(AuthResponse.AUTH_ERROR_USERNAME)
        elif user.password != md5(password):
            return False, AuthResponse.send_error(AuthResponse.AUTH_ERROR_PASSWORD)
        if user.country is None:
            user.country = get_country_by_ip(ip_addr)
        if environ.get('GAME_SERVICE_MODE', 0) == 1 and 'service' not in user.rights:
            return False, AuthResponse.send_message("SERVERS_NOT_WORK_SUKA_BLYAT_MESSAGE")

        await user.add_login(ip_addr, model, vendor, os, devid, platform)

        ugid = md5(f"user_game_id:{user.id}")[:10]
        token = encrypt_token(user.username, ugid, login_type, user.id, game_id)

        await cache_login_data(game_id, username, password, login_type, {'user_game_id': [ugid], 'login_types': [login_type], 'access_token': token, "token_type": "bearer", "expires_at": round(time.time() + 60 * 15)})
    return True, await uncache_login_data(game_id, username, password, login_type)


async def request_auth_token(addr, username, password, login_type, game_id, device_vendor, device_model, os_version, device_id, platform, is_refresh_token):
    if username is None or password is None or game_id is None:
        return AuthResponse.send_error(AuthResponse.AUTH_ERROR_MISSING_DATA)

    if login_type is None:
        if valid_email(username):
            login_type = 'email'
        else:
            return AuthResponse.send_error(AuthResponse.AUTH_ERROR_INVALID_TYPE)

    if login_type not in ('email', 'anon'):
        return AuthResponse.send_error(AuthResponse.AUTH_ERROR_INVALID_TYPE)

    ok, response = await refresh_token(username, password, login_type, game_id, device_vendor, device_model, os_version, device_id, platform, addr, is_refresh_token)
    if not ok:
        logger.info(f'User {username} failed to refresh token: {response}')
        return response
    response['login_types'] = f"[{login_type}]"
    logger.info(f'User {username} successfully refreshed token: {response}')
    return AuthResponse.send_ok(response)


async def pregame_setup(access_token, access_key, client_version):
    token = decrypt_token(access_token)
    if token is None:
        return AuthResponse.send_error(AuthResponse.AUTH_ERROR_LOGIN_FAILED)
    if token.get("expires_at", 0) < time.time():
        return AuthResponse.send_error(AuthResponse.AUTH_ERROR_LOGIN_FAILED)

    if (access_key is None
            or client_version is None
            or client_version not in GameConfig.allowed_versions
            or GameConfig.allowed_versions.get(client_version, None) != access_key):
        return AuthResponse.send_error(AuthResponse.AUTH_ERROR_MISSING_DATA)

    user = await User.load_by_game_and_username(token.get("username"), int(token.get("game")))
    if environ.get('GAME_SERVICE_MODE', 0) == 1 and 'service' not in user.rights:
        return AuthResponse.send_message("SERVERS_NOT_WORK_SUKA_BLYAT_MESSAGE")

    content_url = generate_content_url(client_version, user)
    return AuthResponse.send_ok({"serverIp": environ.get('SERVER_IP'), "serverId": 1, "contentUrl": content_url})


async def get_dlc_file(client_version, file_path, user_id: int):
    if "files.json" in file_path:
        user = await User.load_by_id(int(user_id))

        if str(client_version) == '-1' or str(client_version) == 'add-ons':
            updates = []
        else:
            updates = await get_dlc_file('add-ons', 'files.json', user_id) + await get_dlc_file('-1', 'files.json', user_id)

        if os.path.exists(f"content/updates/{client_version}/"):
            files = get_all_files_in_dir(f"content/updates/{client_version}/")
            for file in files:
                server_path = file
                local_path = '/'.join(server_path.split('/')[3:])

                if local_path in [f.get('localName', 'idk') for f in updates]:
                    continue

                with open(file, 'rb') as f:
                    fdata = f.read()
                    if fdata is None:
                        continue
                    file_hash = hashlib.md5(fdata).hexdigest()
                    updates.append({"serverName": server_path, "localName": local_path, "checksum": file_hash})
        return updates
    if 'content/updates' not in file_path:
        return 'нахуй иди с такими запросами'
    return FileResponse(path=file_path, filename=file_path.split('/')[-1], media_type='multipart/form-data')


async def create_anon_account(addr, game_id, device_model, device_vendor, device_id, platform, os_version):
    if game_id is None:
        return AuthResponse.send_error(AuthResponse.AUTH_ERROR_MISSING_DATA)

    async with User() as user:
        user.game_id = game_id
        user.login_type = 'anon'
        user.created_from_ip = addr
        user.created_from_device = device_id

        await user.save()

        username = md5(f"login:{user.id}")[:12]
        password = md5(username[::-2] + username[1::2])[:20]

        user.username = username
        user.password = md5(password)
        user.date_created = round(datetime.now().timestamp())
        ok, response = await refresh_token(username, password, 'anon', game_id, device_vendor, device_model, os_version, device_id, platform, addr, True)
    if not ok:
        return response
    del response['login_types']
    return AuthResponse.send_ok({"username": user.username, "password": password, "login_type": "anon", "account_id": response.get("user_game_id")} | response)