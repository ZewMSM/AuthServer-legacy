import base64
import hashlib
import json
import re
import subprocess

from Crypto.Cipher import AES

from database import RedisSession


def valid_email(email):
    return bool(re.search(r"^[\w\.\+\-]+\@[\w]+\.[a-z]{2,3}$", email))


def md5(string):
    return hashlib.md5(string.encode('utf-8')).hexdigest()


def get_country_by_ip(ip_addr):
    resp = subprocess.Popen(['whois', ip_addr], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = resp.communicate()
    for _ in stdout.decode('utf-8').split('\n'):
        if 'Country' in _:
            return _.split(' ')[-1]

    return 'XX'


def aes_encrypt(message, initial_vector_string, secret_key):
    key = secret_key.encode('utf-8')
    iv = initial_vector_string.encode('utf-8')
    cipher = AES.new(key, AES.MODE_CFB, iv, segment_size=8)
    ciphertext = cipher.encrypt(message.encode('utf-8'))
    encoded = base64.b64encode(ciphertext).decode('utf-8')
    return encoded


def aes_decrypt(encrypted_data, initial_vector_string, secret_key):
    key = secret_key.encode('utf-8')
    iv = initial_vector_string.encode('utf-8')
    ciphertext = base64.b64decode(encrypted_data)
    cipher = AES.new(key, AES.MODE_CFB, iv, segment_size=8)
    plaintext = cipher.decrypt(ciphertext)
    return plaintext.decode('utf-8')


async def cache_login_data(game_id, username, password, login_type, login_data):
    await RedisSession.hset(f"cached_login_data:{game_id}", md5(f'{username}:{password}:{login_type}'), json.dumps(login_data))


async def uncache_login_data(game_id, username, password, login_type):
    login_data = await RedisSession.hget(f"cached_login_data:{game_id}", md5(f'{username}:{password}:{login_type}'))
    if login_data is not None:
        return json.loads(login_data)
    return {}

def get_all_files_in_dir(dir_path):
    file_list = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list