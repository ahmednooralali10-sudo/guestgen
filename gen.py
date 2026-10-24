#!/usr/bin/env python3
"""
SaMIGEN - Modified Version
- No log file saving
- Saves only uid:pass to FTC.txt
- Account name format: FTC<random>
- Beautiful animated terminal design
"""

import os
import sys
import json
import time
import random
import hashlib
import hmac
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
APP_ID = 100067

OAUTH_REGISTER_URL    = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
OAUTH_TOKEN_URL       = "https://100067.connect.garena.com/oauth/guest/token/grant"
MAJOR_REGISTER_URL    = "https://loginbp.ppmainecoonghj.com/MajorRegister"
NEWBIE_URL            = "https://loginbp.ppmainecoonghj.com/ChooseNewbieChoice"
MAJOR_LOGIN_URL       = "https://loginbp.ppmainecoonghj.com/MajorLogin"
GENERATE_NICKNAME_URL = "https://loginbp.ppmainecoonghj.com/GenerateNickname"

GETLOGIN_HOST_IND   = "client.ind.freefiremobile.com"
GETLOGIN_HOST_OTHER = "clientbp.ggpolarbear.com"

OUTPUT_FILE = "FTC.txt"

# Fixed value from working version — DO NOT randomize
X_GA_SV = "1789636317"


# ══════════════════════════════════════════════════════════════════════════════
#  BEAUTIFUL ANIMATED TERMINAL UI
# ══════════════════════════════════════════════════════════════════════════════
RST = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"
BG_BLACK = "\033[40m"

print_lock = threading.Lock()
file_lock = threading.Lock()
stop_flag = threading.Event()


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def typewriter(text, color=CYAN, delay=0.01, newline=True):
    """Typewriter animation"""
    with print_lock:
        for ch in text:
            sys.stdout.write(f"{color}{ch}{RST}")
            sys.stdout.flush()
            time.sleep(delay)
        if newline:
            sys.stdout.write("\n")
            sys.stdout.flush()


def smooth_print(text, color=CYAN):
    """Instant print with color"""
    with print_lock:
        print(f"{color}{text}{RST}", flush=True)


def spinner(text, duration=0.8, color=MAGENTA):
    """Spinner animation"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end = time.time() + duration
    i = 0
    with print_lock:
        while time.time() < end:
            sys.stdout.write(f"\r{color}{frames[i % len(frames)]} {text}{RST}")
            sys.stdout.flush()
            time.sleep(0.07)
            i += 1
        sys.stdout.write(f"\r{' ' * (len(text) + 4)}\r")
        sys.stdout.flush()


def animate_bar(text, color=GREEN, width=30, duration=0.9):
    """Progress bar animation"""
    with print_lock:
        for i in range(width + 1):
            filled = "█" * i
            empty = "░" * (width - i)
            sys.stdout.write(f"\r{color}{text} [{filled}{empty}] {int(i/width*100)}%{RST}")
            sys.stdout.flush()
            time.sleep(duration / width)
        sys.stdout.write("\n")
        sys.stdout.flush()


def banner():
    """Show animated banner"""
    clear_screen()
    art = [
        "  █████╗ ██████╗ ██╗██╗   ██╗ █████╗ ███╗   ██╗  ",
        " ██╔══██╗██╔══██╗██║╚██╗ ██╔╝██╔══██╗████╗  ██║  ",
        " ███████║██████╔╝██║ ╚████╔╝ ███████║██╔██╗ ██║  ",
        " ██╔══██║██╔══██╗██║  ╚██╔╝  ██╔══██║██║╚██╗██║  ",
        " ██║  ██║██║  ██║██║   ██║   ██║  ██║██║ ╚████║  ",
        " ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝  ",
    ]
    with print_lock:
        for line in art:
            sys.stdout.write(f"{CYAN}{BOLD}{line}{RST}\n")
            sys.stdout.flush()
            time.sleep(0.05)
        print()
    typewriter("            ⚡ Free Fire Account Generator ⚡", MAGENTA, 0.02)
    typewriter("                 ── FTC Edition ──", YELLOW, 0.02)
    print()
    with print_lock:
        print(f"{DIM}{'═' * 62}{RST}")
    print()


def log_step(icon, color, text):
    with print_lock:
        print(f"  {color}{icon}{RST} {text}", flush=True)


def log_ok(text):
    with print_lock:
        print(f"  {GREEN}✓{RST} {text}", flush=True)


def log_err(text):
    with print_lock:
        print(f"  {RED}✗{RST} {text}", flush=True)


def log_info(text):
    with print_lock:
        print(f"  {BLUE}ℹ{RST} {text}", flush=True)


def log_warn(text):
    with print_lock:
        print(f"  {YELLOW}⚠{RST} {text}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  USER-AGENT POOL
# ══════════════════════════════════════════════════════════════════════════════
MSDK_USER_AGENTS = [
    "GarenaMSDK/4.0.42(KB2003 ;Android 13;en;HK;app 2.130.1 2019118332;)",
    "GarenaMSDK/4.0.42(SM-G998B ;Android 14;en;IN;app 2.131.0 2019118527;)",
    "GarenaMSDK/4.0.42(CPH2095 ;Android 12;en;ID;app 2.129.1 2019118142;)",
    "GarenaMSDK/4.0.42(Redmi 2404ARN45A ;Android 13;en;IN;app 2.132.0 2019118721;)",
    "GarenaMSDK/4.0.42(Pixel 6 ;Android 14;en;US;app 2.131.1 2019118602;)",
    "GarenaMSDK/4.0.42(OnePlus 9 Pro ;Android 13;en;IN;app 2.132.2 2019118783;)",
    "GarenaMSDK/4.0.42(Xiaomi 13 Pro ;Android 14;en;ID;app 2.130.2 2019118441;)",
    "GarenaMSDK/4.0.42(realme RMX2189 ;Android 10;en;IN;app 2.130.0 2019118321;)",
]

UNITY_USER_AGENTS = [
    "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2021.3.27f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
    "UnityPlayer/2020.3.45f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
]


def pick_msdk_ua():    return random.choice(MSDK_USER_AGENTS)
def pick_unity_ua():   return random.choice(UNITY_USER_AGENTS)


# ══════════════════════════════════════════════════════════════════════════════
#  INPUT
# ══════════════════════════════════════════════════════════════════════════════
def prompt_int(prompt: str, default: int, min_v: int = 1, max_v: int = 10**9) -> int:
    while True:
        try:
            raw = input(f"  {CYAN}{prompt}{RST}").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return default
        if not raw: return default
        if not raw.isdigit():
            print(f"  {RED}✗ Enter a number between {min_v} and {max_v}{RST}")
            continue
        n = int(raw)
        if not (min_v <= n <= max_v):
            print(f"  {RED}✗ Enter a number between {min_v} and {max_v}{RST}")
            continue
        return n


# ══════════════════════════════════════════════════════════════════════════════
#  PROTOBUF
# ══════════════════════════════════════════════════════════════════════════════
def write_varint(v: int) -> bytes:
    r = []
    while v > 127:
        r.append((v & 0x7F) | 0x80); v >>= 7
    r.append(v); return bytes(r)

def write_varint_field(fn, v): return write_varint((fn << 3) | 0) + write_varint(v)

def write_string_field(fn, v):
    b = v.encode("utf-8")
    return write_varint((fn << 3) | 2) + write_varint(len(b)) + b

def write_bytes_field(fn, v):
    return write_varint((fn << 3) | 2) + write_varint(len(v)) + v

def assemble_proto(fields) -> bytes:
    data = bytearray()
    for k, v in fields.items():
        if isinstance(v, int):
            data.extend(write_varint_field(k, v))
        elif isinstance(v, str):
            data.extend(write_string_field(k, v))
        elif isinstance(v, (bytes, bytearray)):
            data.extend(write_bytes_field(k, bytes(v)))
    return bytes(data)

def aes_encrypt(plain: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(plain, AES.block_size))

def aes_decrypt(ct: bytes) -> bytes:
    return unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(ct), AES.block_size)

def read_varint(data, offset):
    r, s = 0, 0
    while True:
        if offset >= len(data): raise IndexError("eof")
        b = data[offset]; r |= (b & 0x7F) << s; offset += 1
        if not (b & 0x80): break
        s += 7
    return r, offset

def parse_proto(data) -> dict:
    result, offset = {}, 0
    while offset < len(data):
        try:
            tag, offset = read_varint(data, offset)
        except Exception:
            break
        fn, wt = tag >> 3, tag & 0x7
        try:
            if wt == 0:
                v, offset = read_varint(data, offset)
                result[fn] = v
            elif wt == 2:
                ln, offset = read_varint(data, offset)
                v = data[offset:offset + ln]; offset += ln
                try: result[fn] = v.decode("utf-8")
                except: result[fn] = v.hex()
            elif wt == 1:
                result[fn] = data[offset:offset + 8].hex(); offset += 8
            elif wt == 5:
                result[fn] = data[offset:offset + 4].hex(); offset += 4
            else:
                break
        except Exception:
            break
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  XOR
# ══════════════════════════════════════════════════════════════════════════════
XOR_KEY = [0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,
           0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30]

def xor_open_id(open_id: str) -> bytes:
    b = open_id.encode("utf-8")
    return bytes(x ^ XOR_KEY[i % len(XOR_KEY)] for i, x in enumerate(b))


FIELD_22_HEX = (
    "474752450101010062020000a78910bd098e3ff2e4345d59a31db114ea088f37e32e65"
    "212ff96621793d9eb78720d0bf2ac95176569765247ada5eb01376b3b9931794a4946"
    "d76ef8890779f3f2129317e6e1cb2fdcf7b06247cea343b8d4f167eff85a2e1dfe99"
    "b4583a7e1a155dbe7f7f85cff3b223eb77222ec1228f3ee1ef6ce7f8ca24b00a554"
    "e497328812f8df74c82d519ae3e3ceab436eb145e8a517089a7cef6a4efb22214b2"
    "a4b19989b74807584afe5e52825e7ac60e19a596a9bf02d961de6a0ed2515ec6023"
    "fdb7684d9464b97b21c527ce61b6bee4ef30d20a1fa33a996952d44d44e44f2f86c"
    "768aaf2a7808ad60f91048dca0207961ba7c2555c48341b30190debc775edb2cee24"
    "4cf51fca3760ce4388be2db45e80b813b5beb9c784007b7762d7a1e428affc8a3a4"
    "cd76cbaef648a274297fde33233dccd3f272cb77f39a1affe0365a24954111f768f72"
    "0e77535af024bea2b2726c3bac992374755c3deacf09235e6865d456e651680d115a"
    "751a797225eaacdf9a513cf104526e1a32e5296e111a33ae581a63850837921df848"
    "9adfd41ea895b7cf3f5b2e45d538a6e4f032f590ccbb7daf5fa9c50adadee0799661"
    "4c3f957bda349e6c484fdf55970d1943ad7955a76671298b6d98b636b69ebde6bc94"
    "dbd93ac3393a6ae230130445b2d744189167854a5617be2393e7d8fbb5719a1b4754"
    "1ba466167e3e05a6c244f1301ee2035acf94dffc8adbde747d5cd85e35ead3acc372"
    "a59c4220e54bf63f9d80485f3de2518495c1d0f78c911d2da595911fd2a1989cf17"
    "cf3ded5f6c92dea64d675c555c11df92d6c517ca5d0d61a8962f43f76ec7e87596c"
    "8325ebf9ab0f8e6d2eca33c511ceac6980906ebd68c478665591dcecf788ec6ef34c"
    "fbe3fcc279c6147c5bf91cd43cdc9704236"
)


# ══════════════════════════════════════════════════════════════════════════════
#  API CALLS
# ══════════════════════════════════════════════════════════════════════════════
def generate_signature(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"))
    return hmac.new(CLIENT_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def register_guest(session, password, ua):
    payload = {"app_id": APP_ID, "client_type": 2, "password": password, "source": 2}
    signature = generate_signature(payload)
    body = json.dumps(payload, separators=(",", ":"))

    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Signature {signature}",
    }

    resp = session.post(OAUTH_REGISTER_URL, data=body, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Register HTTP {resp.status_code}")

    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Register failed: {data}")

    return str(data["data"]["uid"])


def get_token_legacy(session, uid, password, ua):
    payload = {
        "uid": uid, "password": password,
        "response_type": "token", "client_type": "2",
        "client_secret": CLIENT_SECRET, "client_id": "100067",
    }
    headers = {
        "User-Agent": ua,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }

    resp = session.post(OAUTH_TOKEN_URL, data=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Token HTTP {resp.status_code}")

    data = resp.json()
    at, oid = data.get("access_token"), data.get("open_id")
    if not at or not oid:
        raise Exception(f"Token grant failed")
    return at, oid


def generate_nickname():
    """Generate nickname: FTC + random number"""
    number = random.randint(100000, 999999)
    return f"FTC{number}"


def send_major_register(session, name, access_token, open_id, ua):
    field14_bytes = xor_open_id(open_id)
    fields = {
        1: name, 2: access_token, 3: open_id,
        5: 102000007, 6: 4, 7: 1, 13: 1,
        14: field14_bytes,
        15: "en", 16: 2, 20: "2.133.8", 21: 1,
        22: bytes.fromhex(FIELD_22_HEX),
    }

    plain = assemble_proto(fields)
    encrypted = aes_encrypt(plain)

    headers = {
        "Host": MAJOR_REGISTER_URL.split("/")[2],
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": X_GA_SV,
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Content-Length": str(len(encrypted)),
    }

    resp = session.post(MAJOR_REGISTER_URL, data=encrypted, headers=headers,
                        timeout=30, verify=False)
    if resp.status_code != 200:
        raise Exception(f"MajorRegister HTTP {resp.status_code}")

    return parse_proto(resp.content)


def send_newbie_choice(session, account_id, choice=3, ua=None):
    plain = assemble_proto({1: int(account_id), 2: 1, 3: int(choice)})
    encrypted = aes_encrypt(plain)

    headers = {
        "Host": "loginbp.ppmainecoonghj.com",
        "User-Agent": ua or "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": X_GA_SV,
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Content-Length": str(len(encrypted)),
    }

    resp = session.post(NEWBIE_URL, headers=headers, data=encrypted,
                        timeout=30, verify=False)
    if resp.status_code != 200:
        raise Exception(f"ChooseNewbieChoice HTTP {resp.status_code}")
    return resp


# ══════════════════════════════════════════════════════════════════════════════
#  MAJORLOGIN
# ══════════════════════════════════════════════════════════════════════════════
IP_ADDRESSES = [
    "151.158.158.220", "151.158.158.221", "151.158.158.222", "151.158.158.223",
    "151.158.158.224", "151.158.158.225", "151.158.158.226", "151.158.158.227",
    "151.158.158.228", "151.158.158.229", "151.158.158.230", "151.158.158.231",
    "151.158.158.232", "151.158.158.233", "151.158.158.234", "151.158.158.235",
    "151.158.158.236", "151.158.158.237", "151.158.158.238", "151.158.158.239",
]

random_ip = random.choice(IP_ADDRESSES)


def build_major_login_payload(access_token, open_id, platform_type=4):
    return {
        3: time.strftime("%Y-%m-%d %H:%M:%S"),
        4: "free fire",
        5: 1,
        7: "2.133.9",
        8: "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
        9: "Handheld",
        10: "Vi India",
        11: "WIFI",
        12: 1600,
        13: 720,
        14: "320",
        15: "ARM64 FP ASIMD AES | 2301 | 8",
        16: 2799,
        17: "PowerVR Rogue GE8320",
        18: "OpenGL ES 3.2 build 1.11@5425693",
        19: "Google|9f7d6b8b-b10c-454a-852d-06332cd498eb",
        20: random_ip,
        21: "en",
        22: open_id,
        23: str(platform_type),
        24: "Handheld",
        25: "realme RMX2189",
        26: "TW",
        29: access_token,
        30: 1,
        41: "Vi India",
        42: "WIFI",
        57: "1ac4b80ecf0478a44203bf8fac6120f5",
        60: 19799, 61: 2536, 62: 5056, 64: 2768,
        65: 19999, 66: 2536, 67: 19799,
        73: 1,
        74: "/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/lib/arm64",
        76: 2,
        77: "38f4751a330688ab124c2c804cec90a5|/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/base.apk",
        78: 2, 79: 2, 81: "64", 83: "2019118527",
        86: "OpenGLES3", 87: 3071, 88: 4,
        92: 67920, 93: "android_max",
        94: "KqsHT+UrR1HKqb6+1db+Ofei+NtZr2+hbiBo3yKDL8w+8E3S5qF2IgEEe1fFQFyHRzl4iyHjHp+QsfeLbjJ6+DidTiKxm0ak2uYYa6QR4nAUdlZR",
        95: 111107,
        96: '{"cur_rate":null,"support_etc2":true}',
        97: 1, 98: 1, 99: "4", 100: "4", 102: "",
        104: 83812, 105: 1,
        106: "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|a4332cb1c1a84e51dd77441e4856ed5a",
        107: "1.9393e7b8e53e8aeb",
    }


def send_major_login(session, access_token, open_id, platform_type=4, ua=None):
    body = build_major_login_payload(access_token, open_id, platform_type)
    plain = assemble_proto(body)
    encrypted = aes_encrypt(plain)

    headers = {
        "Host": "loginbp.ppmainecoonghj.com",
        "User-Agent": ua or "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": X_GA_SV,
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Content-Length": str(len(encrypted)),
    }

    resp = session.post(MAJOR_LOGIN_URL, data=encrypted, headers=headers,
                        timeout=30, verify=False)
    if resp.status_code != 200:
        raise Exception(f"MajorLogin HTTP {resp.status_code}")

    PROTOBUF_OFFSET = 64
    if len(resp.content) <= PROTOBUF_OFFSET:
        raise Exception("MajorLogin response too short")

    return parse_proto(resp.content[PROTOBUF_OFFSET:])


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE UID:PASS
# ══════════════════════════════════════════════════════════════════════════════
def save_uid_pass(uid, password):
    """Save uid:pass to FTC.txt"""
    with file_lock:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(f"{uid}:{password}\n")
            f.flush()
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  WORKER
# ══════════════════════════════════════════════════════════════════════════════
def create_one_account(worker_id: int, total: int, counters: dict):
    while not stop_flag.is_set():
        session = None
        try:
            session = requests.Session()
            session.verify = False

            msdk_ua  = pick_msdk_ua()
            unity_ua = pick_unity_ua()

            with print_lock:
                print()
                print(f"  {DIM}{'─' * 58}{RST}")
                print(f"  {MAGENTA}▶ Worker #{worker_id} — new account{RST}")
                print(f"  {DIM}{'─' * 58}{RST}")

            # Password
            random_suffix = hashlib.sha256(os.urandom(16)).hexdigest()[:12].upper()
            password = f"FTC_{random_suffix}"

            # STEP 1
            spinner(f"Registering guest...", 0.5)
            uid = register_guest(session, password, msdk_ua)
            log_ok(f"UID      : {CYAN}{uid}{RST}")

            # STEP 2
            spinner(f"Fetching token...", 0.5)
            access_token, open_id = get_token_legacy(session, uid, password, msdk_ua)
            log_ok(f"Open ID  : {CYAN}{open_id[:30]}...{RST}")

            # STEP 3 - MajorRegister with nickname retry
            nickname = "Unknown"
            account_id = None
            for reg_attempt in range(1, 11):
                nickname = generate_nickname()
                try:
                    spinner(f"Registering nickname {nickname} (try {reg_attempt}/10)...", 0.4)
                    reg_resp = send_major_register(session, nickname,
                                                   access_token, open_id, unity_ua)
                    account_id = reg_resp.get(3)
                    if account_id:
                        log_ok(f"Nickname : {GREEN}{nickname}{RST}")
                        log_ok(f"Acc ID   : {CYAN}{account_id}{RST}")
                        break
                except Exception as e:
                    if reg_attempt < 10:
                        time.sleep(0.3)

            if not account_id:
                raise RuntimeError("MajorRegister failed")

            # STEP 4
            spinner(f"Choosing newbie...", 0.4)
            send_newbie_choice(session, account_id, choice=3, ua=unity_ua)
            log_ok(f"Newbie   : {GREEN}done{RST}")

            # STEP 5
            spinner(f"Logging in...", 0.5)
            login_resp = send_major_login(session, access_token, open_id,
                                          platform_type=4, ua=unity_ua)
            jwt = login_resp.get(8)
            if isinstance(jwt, bytes):
                jwt = jwt.decode("utf-8", errors="ignore")
            if not jwt:
                raise RuntimeError("JWT missing")
            log_ok(f"JWT      : {CYAN}{jwt[:35]}...{RST}")

            # STEP 6 - Save uid:pass
            save_uid_pass(uid, password)
            log_ok(f"Saved    : {GREEN}{uid}:{password}{RST} → {OUTPUT_FILE}")

            with file_lock:
                counters["success"] += 1
                done = counters["success"]

            # Success box
            with print_lock:
                print()
                print(f"  {GREEN}╔{'═' * 58}╗{RST}")
                print(f"  {GREEN}║{RST} {BOLD}{GREEN}✅  ACCOUNT #{done}/{total} CREATED{RST}".ljust(70) + f"{GREEN}║{RST}")
                print(f"  {GREEN}╠{'═' * 58}╣{RST}")
                print(f"  {GREEN}║{RST}  {WHITE}Nickname :{RST} {GREEN}{nickname}{RST}".ljust(72) + f"{GREEN}║{RST}")
                print(f"  {GREEN}║{RST}  {WHITE}UID      :{RST} {CYAN}{uid}{RST}".ljust(72) + f"{GREEN}║{RST}")
                print(f"  {GREEN}║{RST}  {WHITE}Password :{RST} {YELLOW}{password}{RST}".ljust(72) + f"{GREEN}║{RST}")
                print(f"  {GREEN}╚{'═' * 58}╝{RST}")
                print()

            if done >= total:
                stop_flag.set()
                break

        except Exception as e:
            log_err(f"Worker #{worker_id} failed: {str(e)[:80]}")
            if stop_flag.is_set(): break
            time.sleep(2)
        finally:
            if session is not None:
                try: session.close()
                except Exception: pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global stop_flag
    stop_flag.clear()

    banner()

    # Config box
    with print_lock:
        print(f"  {CYAN}┌─[ {BOLD}⚙  CONFIGURATION{RST}{CYAN} ]{'─' * 38}┐{RST}")
    total   = prompt_int("🔢 Accounts to generate : ", default=10, min_v=1)
    threads = prompt_int("🧵 Worker threads       : ", default=5,  min_v=1, max_v=30)
    with print_lock:
        print(f"  {CYAN}└{'─' * 58}┘{RST}")
    print()

    log_info(f"Output file : {YELLOW}{OUTPUT_FILE}{RST}")
    log_info(f"Account name: {YELLOW}FTC<random>{RST}")
    log_info(f"Mode        : {YELLOW}UID:PASS only{RST}")
    print()

    input(f"  {MAGENTA}▶ Press ENTER to start generation...{RST} ")
    print()

    animate_bar("  Initializing", GREEN, 30, 0.8)
    print()

    counters = {"success": 0, "failed": 0}
    start_time = time.time()

    try:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [
                executor.submit(create_one_account, i, total, counters)
                for i in range(1, threads + 1)
            ]
            while counters["success"] < total:
                time.sleep(0.5)
            stop_flag.set()
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}⏹  Stopped by user.{RST}")
        stop_flag.set()

    elapsed = time.time() - start_time

    # Final summary
    print()
    with print_lock:
        print(f"  {MAGENTA}╔{'═' * 58}╗{RST}")
        print(f"  {MAGENTA}║{RST}  {BOLD}{WHITE}📊  FINAL SUMMARY{RST}".ljust(68) + f"{MAGENTA}║{RST}")
        print(f"  {MAGENTA}╠{'═' * 58}╣{RST}")
        print(f"  {MAGENTA}║{RST}  {WHITE}Total Requested :{RST} {CYAN}{total}{RST}".ljust(70) + f"{MAGENTA}║{RST}")
        print(f"  {MAGENTA}║{RST}  {WHITE}Success         :{RST} {GREEN}{counters['success']}{RST}".ljust(70) + f"{MAGENTA}║{RST}")
        print(f"  {MAGENTA}║{RST}  {WHITE}Time Elapsed    :{RST} {YELLOW}{elapsed:.1f}s{RST}".ljust(70) + f"{MAGENTA}║{RST}")
        print(f"  {MAGENTA}║{RST}  {WHITE}Saved To        :{RST} {YELLOW}{OUTPUT_FILE}{RST}".ljust(70) + f"{MAGENTA}║{RST}")
        print(f"  {MAGENTA}╚{'═' * 58}╝{RST}")
        print()

    typewriter("  ✨ Done! Check FTC.txt ✨", GREEN, 0.03)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}⏹  Interrupted by user.{RST}")
        sys.exit(0)
    except Exception as e:
        print(f"\n  {RED}✗ FATAL: {e}{RST}")
        sys.exit(1)
