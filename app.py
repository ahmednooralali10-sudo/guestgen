import os
import sys
import time
import json
import base64
import random
import string
import codecs
import hmac
import hashlib
import threading
import re
import subprocess
import secrets
import signal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, List, Any
from flask import Flask, render_template_string, request, jsonify, send_file

app = Flask(__name__)

class DependencyManager:
    @staticmethod
    def install_requirements() -> None:
        pass

import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from colorama import Fore, Style

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Config:
    C_ = Fore.CYAN
    W_ = Fore.WHITE
    B_ = Style.BRIGHT
    S_ = Style.RESET_ALL

    ACCOUNTS_FILE = "rixor.json"
    API_HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
    API_SECRET_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
    
    AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

    REGION_LANG = {
        "BD": "bn", "IND": "hi", "PK": "ur", "SG": "en", "ID": "id",
        "ME": "ar", "CIS": "ru", "TH": "th", "EU": "en", "US": "en", 
        "SAC": "es", "LK": "en"
    }

class AppState:
    def __init__(self):
        self.exit_flag = False
        self.success_count = 0
        self.lock = threading.Lock()
        self.print_lock = threading.Lock()
        self.ip_counter = 0
        self.ip_lock = threading.Lock()
        self.proxy_list: List[str] = []

state = AppState()

# محرك الأمان المباشر
class SecurityEngine:
    @staticmethod
    def generate_ultra_secure_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_signature(payload_str: str) -> str:
        return hmac.new(
            Config.API_SECRET_KEY.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def encrypt_api_payload(payload_hex: str) -> str:
        raw_bytes = bytes.fromhex(payload_hex)
        cipher = AES.new(Config.AES_KEY, AES.MODE_CBC, Config.AES_IV)
        padded_data = pad(raw_bytes, AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        return encrypted.hex()

class ProtoBuilder:
    @staticmethod
    def encode_varint(n: int) -> bytes:
        if n < 0: return b''
        result = bytearray()
        while True:
            byte = n & 0x7F
            n >>= 7
            if n: byte |= 0x80
            result.append(byte)
            if not n: break
        return bytes(result)

    @classmethod
    def create_field(cls, field_num: int, value: Any) -> bytes:
        if isinstance(value, int):
            return cls.encode_varint((field_num << 3) | 0) + cls.encode_varint(value)
        elif isinstance(value, (str, bytes)):
            encoded_val = value.encode() if isinstance(value, str) else value
            return cls.encode_varint((field_num << 3) | 2) + cls.encode_varint(len(encoded_val)) + encoded_val
        return b''

    @classmethod
    def build(cls, fields_dict: Dict[int, Any]) -> bytes:
        return b''.join(cls.create_field(k, v) for k, v in fields_dict.items())

class NetworkService:
    @staticmethod
    def get_rotated_session() -> requests.Session:
        session = requests.Session()
        with state.ip_lock:
            state.ip_counter += 1
            if state.ip_counter >= 20:
                state.ip_counter = 0
                if state.proxy_list:
                    proxy = random.choice(state.proxy_list)
                    session.proxies = {'http': proxy, 'https': proxy}
        return session

class GarenaAPI:
    def __init__(self):
        self.session = NetworkService.get_rotated_session()

    def perform_major_login(self, access_token: str, open_id: str, lang: str) -> Optional[Dict[str, str]]:
        try:
            payload_parts = [
                b'\x1a\x132025-08-30 05:19:21"\tfree fire(\x01:\x081.114.13B2Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)J\x08HandheldR\nATM MobilsZ\x04WIFI`\xb6\nh\xee\x05r\x03300z\x1fARMv7 VFPv3 NEON VMH | 2400 | 2\x80\x01\xc9\x0f\x8a\x01\x0fAdreno (TM) 640\x92\x01\rOpenGL ES 3.2\x9a\x01+Google|dfa4ab4b-9dc4-454e-8065-e70c733fa53f\xa2\x01\x0e105.235.139.91\xaa\x01\x02',
                lang.encode("ascii"),
                b'\xb2\x01 1d8ec0240ede109973f3321b9354b44d\xba\x01\x014\xc2\x01\x08Handheld\xca\x01\x10Asus ASUS_I005DA\xea\x01@afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390\xf0\x01\x01\xca\x02\nATM Mobils\xd2\x02\x04WIFI\xca\x03 7428b253defc164018c604a1ebbfebdf\xe0\x03\xa8\x81\x02\xe8\x03\xf6\xe5\x01\xf0\x03\xaf\x13\xf8\x03\x84\x07\x80\x04\xe7\xf0\x01\x88\x04\xa8\x81\x02\x90\x04\xe7\xf0\x01\x98\x04\xa8\x81\x02\xc8\x04\x01\xd2\x04=/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/lib/arm\xe0\x04\x01\xea\x04_2087f61c19f57f2af4e7feff0b24d9d9|/data/app/com.dts.freefireth-PdeDnOilCSFn37p1AH_FLg==/base.apk\xf0\x04\x03\xf8\x04\x01\x8a\x05\x0232\x9a\x05\n2019118693\xb2\x05\tOpenGLES2\xb8\x05\xff\x7f\xc0\x05\x04\xe0\x05\xf3F\xea\x05\x07android\xf2\x05pKqsHT5ZLWrYljNb5Vqh//yFRlaPHSO9NWSQsVvOmdhEEn7W+VHNUK+Q+fduA3ptNrGB0Ll0LRz3WW0jOwesLj6aiU7sZ40p8BfUE/FI/jzSTwRe2\xf8\x05\xfb\xe4\x06\x88\x06\x01\x90\x06\x01\x9a\x06\x014\xa2\x06\x014\xb2\x06"GQ@O\x00\x0e^\x00D\x06UA\x0ePM\r\x13hZ\x07T\x06\x0cm\\V\x0ejYV;\x0bU5'
            ]
            
            raw_payload = b''.join(payload_parts)
            raw_payload = raw_payload.replace(b'afcfbf13334be42036e4f742c80b956344bed760ac91b3aff9b607a610ab4390', access_token.encode())
            raw_payload = raw_payload.replace(b'1d8ec0240ede109973f3321b9354b44d', open_id.encode())
            
            encrypted_data = bytes.fromhex(SecurityEngine.encrypt_api_payload(raw_payload.hex()))
            
            headers = {
                'User-Agent': "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                'Accept-Encoding': "deflate, gzip",
                'X-GA-SV': "1789535859",
                'Authorization': "Bearer",
                'X-GA': "v1 1",
                'ReleaseVersion': "OB55",
                'Content-Type': "application/x-www-form-urlencoded",
                'X-Unity-Version': "2018.4.12f1"
            }
            
            resp = self.session.post("https://loginbp.ppmainecoonghj.com/MajorLogin", headers=headers, data=encrypted_data, verify=False, timeout=10)
            
            if resp.status_code == 200:
                jwt_idx = resp.text.find("eyJ")
                if jwt_idx != -1:
                    token = resp.text[jwt_idx:]
                    dot_idx = token.find(".", token.find(".") + 1)
                    if dot_idx != -1:
                        token = token[:dot_idx + 44]
                        payload_b64 = token.split('.')[1]
                        padding = '=' * (4 - len(payload_b64) % 4)
                        decoded_json = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
                        acc_id = decoded_json.get('account_id') or decoded_json.get('external_id')
                        if acc_id:
                            return {"account_id": str(acc_id), "jwt_token": token}
        except Exception:
            pass
        return None

class AccountGenerator:
    @staticmethod
    def save_to_file(data: Dict[str, Any]) -> None:
        try:
            with state.lock:
                accounts = []
                if os.path.exists(Config.ACCOUNTS_FILE):
                    with open(Config.ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                        try:
                            file_data = json.load(f)
                            if isinstance(file_data, list): accounts = file_data
                        except Exception: pass
                
                accounts.append({
                    "uid": data["uid"], "password": data["password"],
                    "account_id": data["account_id"], "name": data["name"],
                    "region": data["region"], "date_created": data["date_created"]
                })
                
                with open(Config.ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(accounts, f, indent=4, ensure_ascii=False)
        except Exception: pass

    @classmethod
    def execute_creation(cls, region: str, prefix: str) -> Optional[Dict[str, Any]]:
        for _ in range(5):
            if state.exit_flag: return None
            try:
                api = GarenaAPI()
                password = SecurityEngine.generate_ultra_secure_password()
                
                reg_payload = json.dumps({"app_id": 100067, "client_type": 2, "password": password, "source": 2}, separators=(',', ':'))
                headers_reg = {
                    "User-Agent": "GarenaMSDK/4.0.44(25028RN03A ;Android 15;ar;EG;app 1.132.1 2019121229;)",
                    "Connection": "Keep-Alive", "Accept": "application/json", "Accept-Encoding": "gzip",
                    "Authorization": f"Signature {SecurityEngine.generate_signature(reg_payload)}",
                    "Content-Type": "application/json; charset=utf-8",
                    "Cookie": "datadome=oYpIhVco_RFvLHe_T9KFd5wuY0gcQuNfrlt4rHJY5QOkwv4TGt8gPMK32MbHuBdzJyfXnXlfzNZT_2tHr2kys8AMYT2~T71QP1S78_7Pdx4JLOXdSrflPT6cOX2vsyJh",
                    "Host": "100067.connect.garena.com",
                }
                
                resp_reg = api.session.post("https://100067.connect.garena.com/api/v2/oauth/guest:register", headers=headers_reg, data=reg_payload, timeout=10, verify=False)
                if resp_reg.status_code != 200 or resp_reg.json().get("code") != 0: continue
                uid = resp_reg.json()['data']['uid']
                
                tok_payload = json.dumps({
                    "client_id": 100067, "client_secret": Config.API_HEX_KEY, "client_type": 2, 
                    "device_id": "02-344afb0e-593c-40b7-92f2-171972f74807", "password": password, 
                    "response_type": "token", "uid": uid,
                }, separators=(',', ':'))
                
                headers_tok = headers_reg.copy()
                headers_tok["Cookie"] = "datadome=y23Z3X17pgkMHEt5zY8dqxC6BIf7WJMgC0RXNbqifHT7t9zajKe_hegFb1Ie9_7JixXpz7FRGVodOn~mWPk_NrqIIhUOXDYqKOahzoRQcyEy77GWEMcdA9_MqPJeM5qv"
                
                resp_tok = api.session.post("https://100067.connect.garena.com/api/v2/oauth/guest/token:grant", headers=headers_tok, data=tok_payload, timeout=10, verify=False)
                if resp_tok.status_code != 200 or resp_tok.json().get("code") != 0: continue
                
                access_token = resp_tok.json()['data']['access_token']
                open_id = resp_tok.json()['data']['open_id']

                keystream = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]
                field = codecs.decode(''.join(chr(ord(open_id[i]) ^ keystream[i % len(keystream)]) for i in range(len(open_id))).encode('unicode_escape').decode('utf-8'), 'unicode_escape').encode('latin1')
                
                name = f"{prefix}{random.randint(10000, 99999)}"
                lang = Config.REGION_LANG.get(region.upper(), "en")
                
                proto = ProtoBuilder.build({1: name, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1, 13: 1, 14: field, 15: lang, 16: 1, 17: 1})
                enc_major = bytes.fromhex(SecurityEngine.encrypt_api_payload(proto.hex()))
                
                headers_major = {
                    "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
                    "Accept-Encoding": "deflate, gzip", "X-GA-SV": "1789535859", "Authorization": "Bearer",
                    "X-GA": "v1 1", "ReleaseVersion": "OB55", "Content-Type": "application/x-www-form-urlencoded",
                    "X-Unity-Version": "2018.4.12f1", "Host": "loginbp.ppmainecoonghj.com"
                }
                api.session.post("https://loginbp.ppmainecoonghj.com/MajorRegister", headers=headers_major, data=enc_major, verify=False, timeout=10)
                
                login_data = api.perform_major_login(access_token, open_id, lang)
                if login_data:
                    account_record = {
                        "uid": int(uid), "password": password, "account_id": login_data["account_id"],
                        "name": name, "region": region, "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    cls.save_to_file(account_record)
                    return account_record
            except Exception: pass
        return None

# واجهة المستخدم مدمجة بالكامل هنا لتفادي أي أخطاء مفقودة
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Rixor Account Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-dark text-light">
    <div class="container mt-5">
        <h2 class="text-center mb-4 text-info">Rixor Generator Web Panel</h2>
        <div class="card bg-secondary text-light p-4 shadow">
            <div class="mb-3">
                <label class="form-label">السيرفر (Server):</label>
                <select id="region" class="form-select">
                    <option value="BD">BD (Bangladesh)</option>
                    <option value="IND">IND (India)</option>
                    <option value="PK">PK (Pakistan)</option>
                    <option value="SG">SG (Singapore)</option>
                    <option value="ID">ID (Indonesia)</option>
                    <option value="ME" selected>ME (Middle East)</option>
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">بادئة الاسم (Prefix):</label>
                <input type="text" id="prefix" class="form-control" value="Rixor">
            </div>
            <div class="mb-3">
                <label class="form-label">العدد المطلوب:</label>
                <input type="number" id="target" class="form-control" value="5">
            </div>
            <button onclick="startGeneration()" class="btn btn-info w-100 fw-bold">بدء التوليد</button>
        </div>

        <div class="mt-4">
            <h4>الحسابات المتولدة (<span id="count">0</span>):</h4>
            <a href="/download" class="btn btn-success btn-sm mb-3">تحميل ملف الحسابات (JSON)</a>
            <div class="table-responsive">
                <table class="table table-dark table-striped">
                    <thead>
                        <tr>
                            <th>الاسم</th>
                            <th>معرف الحساب (Account ID)</th>
                            <th>UID</th>
                            <th>كلمة المرور</th>
                            <th>السيرفر</th>
                        </tr>
                    </thead>
                    <tbody id="accountsTable">
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let interval;

        function startGeneration() {
            const region = document.getElementById('region').value;
            const prefix = document.getElementById('prefix').value;
            const target = document.getElementById('target').value;

            fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({region, prefix, target})
            })
            .then(res => res.json())
            .then(data => {
                alert('تم بدء عملية التوليد في الخلفية!');
                if(interval) clearInterval(interval);
                interval = setInterval(fetchStatus, 2000);
            });
        }

        function fetchStatus() {
            fetch('/status')
            .then(res => res.json())
            .then(data => {
                document.getElementById('count').innerText = data.success_count;
                let tbody = document.getElementById('accountsTable');
                tbody.innerHTML = '';
                data.accounts.forEach(acc => {
                    let row = `<tr>
                        <td>${acc.name}</td>
                        <td>${acc.account_id}</td>
                        <td>${acc.uid}</td>
                        <td><code>${acc.password}</code></td>
                        <td>${acc.region}</td>
                    </tr>`;
                    tbody.innerHTML += row;
                });
            });
        }
    </script>
</body>
</html>
"""

# --- Flask Web Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    region = data.get('region', 'ME')
    prefix = data.get('prefix', 'Rixor')
    try:
        target = int(data.get('target', 1))
    except ValueError:
        target = 1

    state.exit_flag = False
    state.success_count = 0
    
    if os.path.exists(Config.ACCOUNTS_FILE):
        try:
            os.remove(Config.ACCOUNTS_FILE)
        except:
            pass

    def background_task():
        threads_count = min(target, 20)
        with ThreadPoolExecutor(max_workers=threads_count) as executor:
            for _ in range(target):
                if state.exit_flag or state.success_count >= target:
                    break
                executor.submit(AccountGenerator.execute_creation, region, prefix)
        
    threading.Thread(target=background_task).start()
    return jsonify({"status": "started", "target": target})

@app.route('/status')
def status():
    accounts = []
    if os.path.exists(Config.ACCOUNTS_FILE):
        try:
            with open(Config.ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
        except:
            pass
    return jsonify({
        "success_count": len(accounts),
        "accounts": accounts
    })

@app.route('/download')
def download():
    if os.path.exists(Config.ACCOUNTS_FILE):
        return send_file(Config.ACCOUNTS_FILE, as_attachment=True)
    return "No accounts found yet.", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
