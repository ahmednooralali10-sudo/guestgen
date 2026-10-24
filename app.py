#!/usr/bin/env python3
from __future__ import annotations
import base64
import codecs
import hashlib
import hmac
import importlib
import json
import os
import random
import ipaddress
import re
import signal
import uuid
import string
import subprocess
import sys
import threading
import secrets
import shutil
import time
import types
import traceback
from datetime import datetime
from typing import Optional
import asyncio
import socket
import ssl
import gzip
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from google_play_scraper import app as gp_app
import psutil
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.style import Style
from rich import box
from rich.prompt import Prompt, IntPrompt, Confirm

_REQUIRED = {
    "Crypto": "pycryptodome",
    "urllib3": "urllib3",
    "psutil": "psutil",
    "google_play_scraper": "google-play-scraper",
    "socks": "pysocks",
    "rich": "rich",
    "httpx": "httpx",
}

client = httpx.AsyncClient(
    verify=False,
    timeout=httpx.Timeout(15.0, connect=8.0, read=15.0, write=15.0),
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
    http2=False,
)

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PROJECT_ROOT = _HERE
BASE_FOLDER = os.path.join(PROJECT_ROOT, "Generated")
TOKENS_FOLDER = os.path.join(BASE_FOLDER, "TOKENS-JWT")
ACCOUNTS_FOLDER = os.path.join(BASE_FOLDER, "ACCOUNTS")
RARE_ACCOUNTS_FOLDER = os.path.join(BASE_FOLDER, "RARE ACCOUNTS")
COUPLES_ACCOUNTS_FOLDER = os.path.join(BASE_FOLDER, "COUPLE ACCOUNTS")
GHOST_FOLDER = os.path.join(BASE_FOLDER, "GHOST")
GHOST_ACCOUNTS_FOLDER = os.path.join(GHOST_FOLDER, "ACCOUNTS")
GHOST_RARE_FOLDER = os.path.join(GHOST_FOLDER, "RARE ACCOUNTS")
GHOST_COUPLES_FOLDER = os.path.join(GHOST_FOLDER, "COUPLE ACCOUNTS")

for _d in [BASE_FOLDER, TOKENS_FOLDER, ACCOUNTS_FOLDER, RARE_ACCOUNTS_FOLDER,
           COUPLES_ACCOUNTS_FOLDER, GHOST_FOLDER, GHOST_ACCOUNTS_FOLDER,
           GHOST_RARE_FOLDER, GHOST_COUPLES_FOLDER]:
    os.makedirs(_d, exist_ok=True)

settings = types.SimpleNamespace(
    EXIT_FLAG=False,
    SUCCESS_COUNTER=0,
    INFLIGHT_COUNTER=0,
    TARGET_ACCOUNTS=0,
    RARE_COUNTER=0,
    COUPLES_COUNTER=0,
    RARITY_SCORE_THRESHOLD=7,
    ACTIVATE_ON_RUN=True,
    ACTIVATED_COUNTER=0,
    ACTIVATE_MAX_ATTEMPTS=3,
    ACTIVATE_COOLDOWNS=(1.5, 3.0, 6.0),
    DEBUG=False,
    LOCK=threading.Lock(),
    KEY=bytes.fromhex("32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"),
    CLIENT_DATA="SNOWFLAKE  Â·  Guest Account Generator",
    REGION_LANG={
        "ME": "ar", "IND": "hi", "ID": "id", "VN": "vi", "TH": "th", "BD": "bn",
        "PK": "ur", "TW": "zh", "CIS": "ru", "SG": "en", "SAC": "es", "BR": "pt",
    },
    PROJECT_ROOT=PROJECT_ROOT,
    BASE_FOLDER=BASE_FOLDER,
    TOKENS_FOLDER=TOKENS_FOLDER,
    ACCOUNTS_FOLDER=ACCOUNTS_FOLDER,
    RARE_ACCOUNTS_FOLDER=RARE_ACCOUNTS_FOLDER,
    COUPLES_ACCOUNTS_FOLDER=COUPLES_ACCOUNTS_FOLDER,
    GHOST_FOLDER=GHOST_FOLDER,
    GHOST_ACCOUNTS_FOLDER=GHOST_ACCOUNTS_FOLDER,
    GHOST_RARE_FOLDER=GHOST_RARE_FOLDER,
    GHOST_COUPLES_FOLDER=GHOST_COUPLES_FOLDER,
)

def get_region(language_code):
    return settings.REGION_LANG.get(language_code)

def encode_varint(value: int) -> bytes:
    if value < 0:
        return b''
    chunks: list[int] = []
    while True:
        chunk = value & 127
        value >>= 7
        if value:
            chunk |= 128
        chunks.append(chunk)
        if not value:
            break
    return bytes(chunks)
    
def create_varint_field(field_number: int, value: int) -> bytes:
    header = field_number << 3 | 0
    return encode_varint(header) + encode_varint(value)

def create_length_delimited_field(field_number: int, value: str | bytes) -> bytes:
    header = field_number << 3 | 2
    payload = value.encode() if isinstance(value, str) else value
    return encode_varint(header) + encode_varint(len(payload)) + payload

def build_proto_packet(fields: dict) -> bytes:
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = build_proto_packet(value)
            packet.extend(create_length_delimited_field(field, nested))
        elif isinstance(value, int):
            packet.extend(create_varint_field(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(create_length_delimited_field(field, value))
    return bytes(packet)

_AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
_AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

def aes_encrypt_hex(hex_payload: str) -> bytes:
    plaintext = bytes.fromhex(hex_payload)
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size))

def aes_encrypt_to_hex(hex_payload: str) -> str:
    plaintext = bytes.fromhex(hex_payload)
    cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size)).hex()


def aes_decrypt_body(data: bytes) -> bytes:
    if not data or len(data) % 16 != 0:
        return data
    try:
        cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
        return unpad(cipher.decrypt(data), AES.block_size)
    except Exception:
        return data


def _proto_parse_score(buf: bytes) -> int:
    if not buf or len(buf) < 8:
        return -1
    try:
        fields = parse_protobuf_fields(buf)
    except Exception:
        return -1
    if not fields:
        return 0
    score = len(fields)
    for v in fields.values():
        if isinstance(v, bytes) and (b'eyJ' in v or v.startswith(b'http')):
            score += 5
    if 8 in fields or 10 in fields or 21 in fields or 22 in fields or 23 in fields:
        score += 10
    return score


def normalize_login_response(raw: bytes) -> bytes:
    if not raw:
        return raw

    if len(raw) > 64:
        stripped = raw[64:]
        if _proto_parse_score(stripped) > 0:
            return stripped

    if len(raw) > 64:
        return raw[64:]
    return raw

def AutoUpdate(retries: int = 3, delay: float = 1.5):

    spinner = ['â ', 'â ', 'â ¹', 'â ¸', 'â ¼', 'â ´', 'â ¦', 'â §', 'â ', 'â ']
    last_error = None
    _CYAN = '\x1b[36m'
    _BRIGHT_CYAN = '\x1b[96m'
    _GREY = '\x1b[90m'
    _RST = '\x1b[0m'
    _GREEN = '\x1b[32m'
    _YELLOW = '\x1b[33m'
    _RED = '\x1b[31m'
    _BOLD = '\x1b[1m'

    stop_spin = threading.Event()
    spin_lock = threading.Lock()

    def _clear_line() -> None:
        sys.stdout.write('\r' + ' ' * 96 + '\r')
        sys.stdout.flush()

    def _spinner_loop() -> None:
        i = 0
        while not stop_spin.is_set():
            frame = spinner[i % len(spinner)]

            line = (
                f'  {_CYAN}{frame}{_RST}  '
                f'{_BRIGHT_CYAN}{_BOLD}âï¸ SNOWFLAKE{_RST}  '
                f'{_GREY}Connecting to version serviceâ¦{_RST}'
            )
            with spin_lock:
                sys.stdout.write('\r' + line)
                sys.stdout.flush()
            i += 1
            stop_spin.wait(0.08)

    def _stop_spinner() -> None:
        stop_spin.set()
        if spin_thread.is_alive():
            spin_thread.join(timeout=1.0)
        with spin_lock:
            _clear_line()

    spin_thread = threading.Thread(target=_spinner_loop, name='ver-spin', daemon=True)
    spin_thread.start()

    try:
        for attempt in range(1, retries + 1):
            try:
                result = gp_app('com.dts.freefiremax', lang='en', country='sg')
                version = result['version']
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(delay)
                continue
            try:
                with httpx.Client(verify=False, timeout=15.0, trust_env=False) as session:
                    r = session.get(
                        'https://version.ffmax.purplevioleto.com/live/ver.php',
                        params={
                            'version': version, 'lang': 'en', 'device': 'android',
                            'channel': 'android_max', 'appstore': 'googleplay_max', 'region': 'SG',
                            'whitelist_version': '1.3.0', 'whitelist_sp_version': '1.0.0',
                            'device_name': 'google G011A', 'device_CPU': 'ARMv7 VFPv3 NEON VMH',
                            'device_GPU': 'Adreno (TM) 640', 'device_mem': '1993',
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
            except (httpx.HTTPError, ValueError) as e:
                last_error = e
                if attempt < retries:
                    time.sleep(delay)
                continue
            try:
                remote_version = data['remote_version'].rstrip('/')
                release_version = data['latest_release_version']
                if not remote_version or not release_version:
                    last_error = ValueError('empty remote_version or release_version')
                    if attempt < retries:
                        time.sleep(delay)
                    continue
                _stop_spinner()
                print(
                    f'  {_GREEN}â{_RST}  Client {_BOLD}{remote_version}{_RST}'
                    f'  Â·  Release {_BOLD}{release_version}{_RST}'
                )
                return (version, remote_version, release_version)
            except KeyError as e:
                last_error = e
                if attempt < retries:
                    time.sleep(delay)
                continue
    finally:
        if not stop_spin.is_set():
            _stop_spinner()

    print(f'  {_RED}â{_RST}  AutoUpdate failed after {retries} attempts. Last: {last_error}')
    return (None, None, None)



ACCOUNT_RARITY_PATTERNS: dict[str, list] = {'REPEATED_DIGITS_4': ['(\\d)\\1{3,}', 3], 'REPEATED_DIGITS_3': ['(\\d)\\1\\1(\\d)\\2\\2', 2], 'SEQUENTIAL_5': ['(12345|23456|34567|45678|56789)', 4], 'SEQUENTIAL_4': ['(0123|1234|2345|3456|4567|5678|6789|9876|8765|7654|6543|5432|4321|3210)', 3], 'PALINDROME_6': ['^(\\d)(\\d)(\\d)\\3\\2\\1$', 5], 'PALINDROME_4': ['^(\\d)(\\d)\\2\\1$', 3], 'SPECIAL_COMBINATIONS_HIGH': ['(69|420|1337|007)', 4], 'SPECIAL_COMBINATIONS_MED': ['(100|200|300|400|500|666|777|888|999)', 2], 'QUADRUPLE_DIGITS': ['(1111|2222|3333|4444|5555|6666|7777|8888|9999|0000)', 4], 'MIRROR_PATTERN_HIGH': ['^(\\d{2,3})\\1$', 3], 'MIRROR_PATTERN_MED': ['(\\d{2})0\\1', 2], 'GOLDEN_RATIO': ['1618|0618', 3]}

def check_account_rarity(account_data: dict) -> tuple[bool, str | None, str | None, int]:
    account_id: str = account_data.get('account_id', '')
    if account_id == 'N/A' or not account_id:
        return (False, None, None, 0)
    rarity_score = 0
    detected_patterns: list[str] = []
    for pattern_name, (pattern, score) in ACCOUNT_RARITY_PATTERNS.items():
        if re.search(pattern, account_id):
            rarity_score += score
            detected_patterns.append(pattern_name)
    digits = [int(d) for d in account_id if d.isdigit()]
    if len(set(digits)) == 1 and len(digits) >= 4:
        rarity_score += 5
        detected_patterns.append('UNIFORM_DIGITS')
    if len(digits) >= 4:
        diffs = [digits[i + 1] - digits[i] for i in range(len(digits) - 1)]
        if len(set(diffs)) == 1:
            rarity_score += 4
            detected_patterns.append('ARITHMETIC_SEQUENCE')
    if len(account_id) <= 8 and account_id.isdigit() and (int(account_id) < 1000000):
        rarity_score += 3
        detected_patterns.append('LOW_ACCOUNT_ID')
    if rarity_score >= settings.RARITY_SCORE_THRESHOLD:
        reason = f'Account ID {account_id} â Score: {rarity_score} â Patterns: {', '.join(detected_patterns)}'
        return (True, 'RARE_ACCOUNT', reason, rarity_score)
    return (False, None, None, rarity_score)
POTENTIAL_COUPLES: dict[str, dict] = {}
COUPLES_LOCK = threading.Lock()
ACCOUNT_COUPLES_PATTERNS: dict[str, list[str]] = {'MATCHING_PAIRS': ['(\\d{2})01.*\\d{2}02', '(\\d{2})11.*\\d{2}12', '(\\d{2})21.*\\d{2}22'], 'COMPLEMENTARY_DIGITS': ['.*13.*14$', '.*07.*08$', '.*51.*52$'], 'LOVE_NUMBERS': ['.*520.*521$', '.*1314$']}

def _are_couple(id1: str, id2: str) -> tuple[bool, str | None]:
    try:
        if abs(int(id1) - int(id2)) == 1:
            return (True, f'Sequential Account IDs: {id1} & {id2}')
    except ValueError:
        pass
    if id1 and id2 and (id1 == id2[::-1]):
        return (True, f'Mirror Account IDs: {id1} & {id2}')
    '\n    try:\n        total = int(id1) + int(id2)\n        if total % 1_000 == 0 or total % 10_000 == 0:\n            return True, f"Complementary sum: {id1} + {id2} = {total}"\n    except ValueError:\n        pass\n    \n    # Love numbers\n    for love_num in ("520", "521", "1314", "3344"):\n        if love_num in id1 and love_num in id2:\n            return True, f"Both contain love number: {love_num}"\n    '
    return (False, None)

def check_account_couples(account_data: dict, thread_id: int) -> tuple[bool, str | None, dict | None]:
    account_id: str = account_data.get('account_id', '')
    if account_id == 'N/A' or not account_id:
        return (False, None, None)
    with COUPLES_LOCK:
        for stored_id, stored_data in list(POTENTIAL_COUPLES.items()):
            matched, reason = _are_couple(account_id, stored_data.get('account_id', ''))
            if matched:
                del POTENTIAL_COUPLES[stored_id]
                return (True, reason, stored_data)
        POTENTIAL_COUPLES[account_id] = {'uid': account_data.get('uid', ''), 'account_id': account_id, 'name': account_data.get('name', ''), 'password': account_data.get('password', ''), 'region': account_data.get('region', ''), 'thread_id': thread_id, 'timestamp': datetime.now().isoformat()}
    return (False, None, None)

console = Console(force_terminal=True, highlight=False)
_live: Optional[Live] = None
_live_lock = threading.Lock()
_recent_accounts: list[dict] = []
_recent_lock = threading.Lock()
_MAX_RECENT = 8
_SUMMARY: dict = {}
_STATUS = {'current': 0, 'total': 0, 'rare': 0, 'couples': 0, 'region': '', 'is_ghost': False, 'threads_alive': 0, 'elapsed': 0.0, 'speed': 0.0, 'last_event': ''}

class Colors:
    BRIGHT = 'bold'
    RESET = ''

def get_random_color() -> str:
    return random.choice(['bright_cyan', 'cyan', 'bright_white', 'blue'])

def clear_screen() -> None:
    console.clear()

def safe_exit(signum=None, frame=None) -> None:
    settings.EXIT_FLAG = True
    try:
        _proxy_hold.set()
    except Exception:
        pass
    try:
        stop_live()
    except Exception:
        pass
    try:
        flush_saves()
    except Exception:
        pass
    try:
        console.print('\n[bold yellow]ð¨ Safe exit triggered. Saving & closing...[/]')
    except Exception:
        pass
    os._exit(0)

def display_banner() -> None:
    art = (
        "[bold bright_cyan]"
        "   ââââââââââââ   âââ âââââââ âââ    ââââââââââââââ      ââââââ âââ  âââââââââââ\n"
        "   âââââââââââââ  âââââââââââââââ    ââââââââââââââ     âââââââââââ ââââââââââââ\n"
        "   ââââââââââââââ ââââââ   ââââââ ââ âââââââââ  âââ     âââââââââââââââ ââââââ  \n"
        "   âââââââââââââââââââââ   âââââââââââââââââââ  âââ     âââââââââââââââ ââââââ  \n"
        "   âââââââââââ ââââââââââââââââââââââââââââ     âââââââââââ  ââââââ  âââââââââââ\n"
        "   âââââââââââ  âââââ âââââââ  ââââââââ âââ     âââââââââââ  ââââââ  âââââââââââ"
        "[/]"
    )
    console.print()
    console.print(Align.center(Text.from_markup(art)))
    console.print(Align.center(Text.from_markup("[dim]ââââââââââââââââââ â¦ ââââââââââââââââââ[/]")))
    console.print(Align.center(Text.from_markup(f"[bold bright_white]{settings.CLIENT_DATA}[/]")))
    console.print()

def print_success(message: str) -> None:
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = f'[green]â {message}[/]'
            return
    console.print(f'[bold green]â {message}[/]')

def print_error(message: str) -> None:
    if not getattr(settings, 'DEBUG', False):
        return
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = f'[red]â {message}[/]'
            return
    console.print(f'[bold red]â {message}[/]')

def print_warning(message: str) -> None:
    if not getattr(settings, 'DEBUG', False):
        return
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = f'[yellow]â ï¸  {message}[/]'
            return
    console.print(f'[bold yellow]â ï¸  {message}[/]')

def print_info(message: str) -> None:
    if not getattr(settings, 'DEBUG', False):
        return
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = f'[blue]ð¢  {message}[/]'
            return
    console.print(f'[bold blue]ð¢  {message}[/]')

def debug_log(message: str, exc: BaseException | None = None) -> None:
    if not getattr(settings, 'DEBUG', False):
        return
    console.print(f'[dim]DEBUG[/] {message}')
    if exc is not None:
        tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        for line in tb.rstrip().splitlines():
            console.print(f'[dim]DEBUG[/] {line}')

def print_rare(message: str) -> None:
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = f'[cyan]ð {message}[/]'
            return
    console.print(f'[bold cyan]ð {message}[/]')

def _console_width() -> int:
    try:
        return max(console.width or 80, 60)
    except Exception:
        return 80

def _build_progress_table() -> Table:
    width = _console_width()
    name_w = max(10, min(18, width // 8))
    uid_w = max(10, min(16, width // 7))
    id_w = max(10, min(14, width // 8))
    pass_w = max(12, min(22, width // 5))
    region_w = max(6, min(10, width // 12))
    table = Table(box=box.ROUNDED, expand=True, show_header=True, header_style='bold bright_white', border_style='bright_cyan', pad_edge=False, width=width - 2)
    table.add_column('#', style='dim', width=4, justify='right')
    table.add_column('Name', style='bright_white', width=name_w, overflow='ellipsis')
    table.add_column('UID', style='bright_cyan', width=uid_w, overflow='ellipsis')
    table.add_column('Account ID', style='bright_yellow', width=id_w, overflow='ellipsis')
    table.add_column('Password', style='bright_green', width=pass_w, overflow='ellipsis')
    table.add_column('Region', style='magenta', width=region_w, justify='center')
    table.add_column('Flags', width=10, justify='center')
    with _recent_lock:
        rows = list(_recent_accounts[-_MAX_RECENT:])
    for idx, acc in enumerate(rows, 1):
        flags = []
        if acc.get('rare'):
            flags.append('[cyan]ð[/]')
        if acc.get('couple'):
            flags.append('[#FF69B4]ð[/]')
        flag_str = ' '.join(flags) if flags else 'â'
        table.add_row(str(acc.get('count', idx)), str(acc.get('name', ''))[:name_w], str(acc.get('uid', ''))[:uid_w], str(acc.get('account_id', 'N/A'))[:id_w], str(acc.get('password', ''))[:pass_w], str(acc.get('region', ''))[:region_w], flag_str)
    if not rows:
        table.add_row('â', 'waitingâ¦', 'â', 'â', 'â', 'â', 'â')
    return table

def _build_status_panel() -> Panel:
    width = _console_width()
    s = _STATUS
    pct = s['current'] / s['total'] * 100 if s['total'] else 0.0
    mode = 'GHOST' if s['is_ghost'] else s['region'] or 'â'
    bar_len = max(10, min(40, width // 3))
    filled = int(bar_len * pct / 100)
    bar = 'â' * filled + 'â' * (bar_len - filled)
    header = Text()
    header.append(' ð Progress  ', style='bold bright_white')
    header.append(f'{s['current']}/{s['total']} ', style='bold green')
    header.append(f'({pct:.1f}%)  ', style='dim')
    header.append(f'[{bar}]  ', style='bright_blue')
    header.append(f'ð {s['rare']}  ', style='bold cyan')
    header.append(f'ð {s['couples']}  ', style='bold #FF69B4')
    activated_n = getattr(settings, 'ACTIVATED_COUNTER', 0)
    if activated_n or getattr(settings, 'ACTIVATE_ON_RUN', False):
        header.append(f'â¡ {activated_n}  ', style='bold green')
    header.append(f'ð {mode}  ', style='magenta')
    header.append(f'â¡ {s['speed']:.2f}/s  ', style='yellow')
    header.append(f'â± {s['elapsed']:.1f}s  ', style='dim')
    if _SUMMARY.get('use_proxy'):
        header.append('Proxy: ON', style='bold yellow')
    else:
        header.append('Proxy: OFF', style='dim')
    event = Text.from_markup(s.get('last_event') or '[dim]ready[/]')
    body = Group(header, event)
    return Panel(body, box=box.ROUNDED, border_style='bright_cyan', width=width - 2, padding=(0, 1))

def _render_live() -> Group:
    return Group(_build_status_panel(), _build_progress_table())

def start_live(total: int, region: str, is_ghost: bool, summary: Optional[dict]=None) -> None:
    global _live
    with _live_lock:
        _STATUS.update({'current': 0, 'total': total, 'rare': 0, 'couples': 0, 'region': region, 'is_ghost': is_ghost, 'threads_alive': 0, 'elapsed': 0.0, 'speed': 0.0, 'last_event': '[dim]startingâ¦[/]'})
        if summary is not None:
            _SUMMARY.clear()
            _SUMMARY.update(summary)
        with _recent_lock:
            _recent_accounts.clear()
        _live = Live(_render_live(), console=console, refresh_per_second=4, transient=False, vertical_overflow='visible')
        _live.start()

def update_live(current: Optional[int]=None, rare: Optional[int]=None, couples: Optional[int]=None, elapsed: Optional[float]=None, speed: Optional[float]=None, last_event: Optional[str]=None, render: bool=True) -> None:
    with _live_lock:
        if current is not None:
            _STATUS['current'] = max(_STATUS['current'], int(current))
        if rare is not None:
            _STATUS['rare'] = max(_STATUS['rare'], int(rare))
        if couples is not None:
            _STATUS['couples'] = max(_STATUS['couples'], int(couples))
        if elapsed is not None:
            _STATUS['elapsed'] = max(_STATUS['elapsed'], float(elapsed))
        if speed is not None:
            _STATUS['speed'] = float(speed)
        if last_event is not None:
            _STATUS['last_event'] = last_event
        if render and _live is not None:
            try:
                _live.update(_render_live())
            except Exception:
                pass

def stop_live() -> None:
    global _live
    live = None
    with _live_lock:
        live = _live
        _live = None
    if live is not None:
        try:
            live.stop()
        except Exception:
            pass

def print_registration_status(count: int, total: int, name: str, uid: str, password: str, account_id: str, region: str, is_ghost: bool=False) -> None:
    entry = {'count': count, 'name': name, 'uid': uid, 'password': password, 'account_id': account_id, 'region': 'GHOST' if is_ghost else region, 'rare': False, 'couple': False}
    with _recent_lock:
        _recent_accounts.append(entry)
        if len(_recent_accounts) > _MAX_RECENT * 2:
            del _recent_accounts[:-_MAX_RECENT]
    with _live_lock:
        if _live is not None:
            _STATUS['current'] = max(_STATUS['current'], int(count))
            _STATUS['last_event'] = f'[green]â #{count} {name}[/]'
            return
    console.print(f'[bold green]ð Registration {count}/{total}[/]\n  ð¤ Name:       {name}\n  ð UID:        {uid}\n  ð¢ Account ID: {account_id}\n  ð Password:   {password}\n  ð {('Mode: GHOST' if is_ghost else f'Region: {region}')}\n')

def print_rarity_found(account_data: dict, rarity_type: str, reason: str, rarity_score: int) -> None:
    uid = account_data.get('uid', '')
    with _recent_lock:
        for acc in reversed(_recent_accounts):
            if acc.get('uid') == uid:
                acc['rare'] = True
                break
    msg = f'[bold cyan]ð RARE #{rarity_score}[/] {account_data.get('name', '')} (ID {account_data.get('account_id', 'N/A')}) â {rarity_type}'
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = msg
            return
    console.print(f'\n[bold cyan]ð RARE ACCOUNT FOUND![/]\n[cyan]ð¯ Type:        {rarity_type}[/]\n[cyan]â­ Score:       {rarity_score}[/]\n[cyan]ð¤ Name:        {account_data['name']}[/]\n[cyan]ð UID:         {account_data['uid']}[/]\n[cyan]ð¢ Account ID:  {account_data.get('account_id', 'N/A')}[/]\n[cyan]ð Reason:      {reason}[/]\n[cyan]ð§µ Thread:      {account_data.get('thread_id', 'N/A')}[/]\n[cyan]ð Region:      {account_data.get('region', 'N/A')}[/]\n')

def print_couples_found(account1: dict, account2: dict, reason: str) -> None:
    for a in (account1, account2):
        uid = a.get('uid', '')
        with _recent_lock:
            for acc in reversed(_recent_accounts):
                if acc.get('uid') == uid:
                    acc['couple'] = True
                    break
    msg = f'[bold #FF69B4]ð COUPLE[/] {account1.get('name', '')} â {account2.get('name', '')} â {reason}'
    with _live_lock:
        if _live is not None:
            _STATUS['last_event'] = msg
            return
    console.print(f'\n[bold #FF69B4]ð COUPLES ACCOUNT FOUND![/]\n[#FF69B4]ð Reason:    {reason}[/]\n[#FF69B4]ð¤ Account 1: {account1['name']} (ID: {account1.get('account_id', 'N/A')}) - Thread {account1.get('thread_id', 'N/A')}[/]\n[#FF69B4]ð¤ Account 2: {account2['name']} (ID: {account2.get('account_id', 'N/A')}) - Thread {account2.get('thread_id', 'N/A')}[/]\n[#FF69B4]ð UIDs:      {account1['uid']} & {account2['uid']}[/]\n[#FF69B4]ð Region:    {account1.get('region', 'N/A')}[/]\n')
_FILE_LOCKS: dict[str, threading.Lock] = {}
_LOCK_REGISTRY = threading.Lock()

def _get_file_lock(filename: str) -> threading.Lock:
    with _LOCK_REGISTRY:
        if filename not in _FILE_LOCKS:
            _FILE_LOCKS[filename] = threading.Lock()
        return _FILE_LOCKS[filename]

def _atomic_json_write(filepath: str, data: list) -> None:
    tmp = filepath + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, filepath)

def _load_json_list(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def save_normal_account(account_data: dict, region: str, is_ghost: bool=False) -> bool:
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_ACCOUNTS_FOLDER, 'ghost.json')
        else:
            filepath = os.path.join(settings.ACCOUNTS_FOLDER, f'accounts-{region}.json')
        entry = {'uid': account_data['uid'], 'password': account_data['password'], 'account_id': account_data.get('account_id', 'N/A'), 'name': account_data['name'], 'region': 'Not Locked Yet' if is_ghost else region, 'date_created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'thread_id': account_data.get('thread_id', 'N/A')}
        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if account_data.get('account_id', 'N/A') in {r.get('account_id') for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True
    except Exception as e:
        print_error(f'Error saving account: {e}')
        return False

def save_jwt_token(account_data: dict, jwt_token: str, region: str, is_ghost: bool=False) -> bool:
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_FOLDER, 'tokens-ghost.json')
        else:
            filepath = os.path.join(settings.TOKENS_FOLDER, f'tokens-{region}.json')
        entry = {'uid': account_data['uid'], 'account_id': account_data.get('account_id', 'N/A'), 'jwt_token': jwt_token, 'name': account_data['name'], 'password': account_data['password'], 'date_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'region': 'Not Locked Yet' if is_ghost else region, 'thread_id': account_data.get('thread_id', 'N/A')}
        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if account_data.get('account_id', 'N/A') in {r.get('account_id') for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True
    except Exception as e:
        print_error(f'Error saving JWT token: {e}')
        return False

def save_rare_account(account_data: dict, rarity_type: str, reason: str, rarity_score: int, is_ghost: bool=False) -> bool:
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_RARE_FOLDER, 'rare-ghost.json')
        else:
            region = account_data.get('region', 'UNKNOWN')
            filepath = os.path.join(settings.RARE_ACCOUNTS_FOLDER, f'rare-{region}.json')
        entry = {'uid': account_data['uid'], 'password': account_data['password'], 'account_id': account_data.get('account_id', 'N/A'), 'name': account_data['name'], 'region': 'Not Locked Yet' if is_ghost else account_data.get('region', 'UNKNOWN'), 'rarity_type': rarity_type, 'rarity_score': rarity_score, 'reason': reason, 'date_identified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'jwt_token': account_data.get('jwt_token', ''), 'thread_id': account_data.get('thread_id', 'N/A')}
        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if account_data.get('account_id', 'N/A') in {r.get('account_id') for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True
    except Exception as e:
        print_error(f'Error saving rare account: {e}')
        return False

def save_couples_account(account1: dict, account2: dict, reason: str, is_ghost: bool=False) -> bool:
    try:
        if is_ghost:
            filepath = os.path.join(settings.GHOST_COUPLES_FOLDER, 'couples-ghost.json')
        else:
            region = account1.get('region', 'UNKNOWN')
            filepath = os.path.join(settings.COUPLES_ACCOUNTS_FOLDER, f'couples-{region}.json')
        couple_id = f'{account1.get('account_id', 'N/A')}_{account2.get('account_id', 'N/A')}'
        entry = {'couple_id': couple_id, 'account1': {'uid': account1['uid'], 'password': account1['password'], 'account_id': account1.get('account_id', 'N/A'), 'name': account1['name'], 'thread_id': account1.get('thread_id', 'N/A')}, 'account2': {'uid': account2['uid'], 'password': account2['password'], 'account_id': account2.get('account_id', 'N/A'), 'name': account2['name'], 'thread_id': account2.get('thread_id', 'N/A')}, 'reason': reason, 'region': 'Not Locked Yet' if is_ghost else account1.get('region', 'UNKNOWN'), 'date_matched': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        lock = _get_file_lock(filepath)
        with lock:
            records = _load_json_list(filepath)
            if couple_id in {r.get('couple_id') for r in records}:
                return False
            records.append(entry)
            _atomic_json_write(filepath, records)
        return True
    except Exception as e:
        print_error(f'Error saving couples account: {e}')
        return False

OAUTH_TOKEN_URL = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant"
OAUTH_REGISTER_URL = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest:register"
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

CLIENT_VERSION, REMOTE_VERSION, RELEASE_VERSION = AutoUpdate()
CLIENT_VERSION_CODE = "2019118525"
LOGIN_URL = "https://loginbp.ggpolarbear.com"
PROXY_LIST: list[str] = []
_BLOCKED_STATUS = {400, 429, 503}
_PROXY_SWITCH_COOLDOWN = 8.0
_MIN_GAP_PER_PROXY = 0.30
_COOLDOWN_RATE_LIMITED = 20.0
_COOLDOWN_UNAVAILABLE = 45.0
_REQUEST_TIMEOUT = 15.0
_CONNECT_TIMEOUT = 8.0
_MAX_HTTP_RETRIES = 3
_RETRY_SLEEP = 0.35
_USE_PROXIES = False
_proxy_pool: list[str] = []
_proxy_index = 0
_proxy_lock = threading.RLock()
_proxy_hold = threading.Event()
_proxy_hold.set()
_rotating = False
_last_switch_ts = 0.0
_prompt_pending = False
_prompt_lock = threading.Lock()
_proxy_cooldowns: dict[str, float] = {}
_proxy_last_request: dict[str, float] = {}
_proxy_gap_locks: dict[str, threading.Lock] = {}

def set_proxy_mode(enabled: bool) -> None:
    global _USE_PROXIES, _proxy_pool, _proxy_index, _last_switch_ts, _rotating, _prompt_pending
    with _proxy_lock:
        _USE_PROXIES = bool(enabled)
        _proxy_pool = [p.strip() for p in PROXY_LIST if p and p.strip()]
        _proxy_index = 0
        _last_switch_ts = 0.0
        _rotating = False
        _prompt_pending = False
        _proxy_cooldowns.clear()
        _proxy_last_request.clear()
        _proxy_hold.set()


def proxies_available() -> bool:
    return any(p.strip() for p in PROXY_LIST)


def is_using_proxies() -> bool:
    return _USE_PROXIES


def is_proxy_prompt_pending() -> bool:
    return _prompt_pending


def wait_if_held() -> None:
    while not settings.EXIT_FLAG:
        if _proxy_hold.is_set():
            return
        time.sleep(0.05)


async def async_wait_if_held() -> None:
    while not settings.EXIT_FLAG:
        if _proxy_hold.is_set():
            return
        await asyncio.sleep(0.05)


def current_proxy_label() -> str:
    if not _USE_PROXIES:
        return 'Direct'
    with _proxy_lock:
        if not _proxy_pool:
            return 'Proxy'
        return _proxy_pool[_proxy_index % len(_proxy_pool)]


def _proxy_key(url: Optional[str]) -> str:
    return url or '__direct__'


def cool_down_proxy(url: Optional[str], seconds: float) -> None:
    if not url:
        return
    key = _proxy_key(url)
    with _proxy_lock:
        _proxy_cooldowns[key] = max(_proxy_cooldowns.get(key, 0.0), time.time() + seconds)


async def _async_throttle_proxy(url: Optional[str]) -> None:
    key = _proxy_key(url)
    lock = _proxy_gap_locks.setdefault(key, threading.Lock())
    wait_for = 0.0
    with lock:
        now = time.time()
        elapsed = now - _proxy_last_request.get(key, 0.0)
        if elapsed < _MIN_GAP_PER_PROXY:
            wait_for = _MIN_GAP_PER_PROXY - elapsed
        else:
            _proxy_last_request[key] = now
    if wait_for > 0:
        await asyncio.sleep(wait_for)
        with lock:
            _proxy_last_request[key] = time.time()


def _pick_proxy_url() -> Optional[str]:
    if not _USE_PROXIES:
        return None
    with _proxy_lock:
        if not _proxy_pool:
            return None
        now = time.time()
        n = len(_proxy_pool)
        for i in range(n):
            idx = (_proxy_index + i) % n
            candidate = _proxy_pool[idx]
            if now >= _proxy_cooldowns.get(candidate, 0.0):
                _proxy_index = idx
                return candidate
        return _proxy_pool[_proxy_index % n]


def get_request_proxies() -> Optional[dict]:
    wait_if_held()
    url = _pick_proxy_url()
    if not url:
        return None
    return {'http': url, 'https': url}


def _current_proxy_url() -> Optional[str]:
    if not _USE_PROXIES:
        return None
    return _pick_proxy_url()


async def http_post(
    url: str,
    *,
    headers: dict | None = None,
    content=None,
    data=None,
    json_body=None,
    timeout: float | None = None,
) -> httpx.Response:

    await async_wait_if_held()
    proxy = _current_proxy_url()
    await _async_throttle_proxy(proxy)
    to = timeout if timeout is not None else _REQUEST_TIMEOUT
    timeout_cfg = httpx.Timeout(to, connect=_CONNECT_TIMEOUT, read=to, write=to)
    kwargs: dict = {'headers': headers or {}, 'timeout': timeout_cfg}
    if content is not None:
        kwargs['content'] = content
    elif data is not None:
        kwargs['data'] = data
    elif json_body is not None:
        kwargs['json'] = json_body

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_HTTP_RETRIES + 1):
        try:
            if proxy:
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=timeout_cfg,
                    proxy=proxy,
                    limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
                    http2=False,
                ) as proxy_client:
                    resp = await proxy_client.post(url, **kwargs)
            else:
                resp = await client.post(url, **kwargs)

            if resp.status_code == 429:
                cool_down_proxy(proxy, _COOLDOWN_RATE_LIMITED)
                handle_blocked_status(429)
                proxy = _current_proxy_url()
                await _async_throttle_proxy(proxy)
                await asyncio.sleep(_RETRY_SLEEP)
                continue
            if resp.status_code == 503:
                cool_down_proxy(proxy, _COOLDOWN_UNAVAILABLE)
                handle_blocked_status(503)
                proxy = _current_proxy_url()
                await _async_throttle_proxy(proxy)
                await asyncio.sleep(_RETRY_SLEEP)
                continue
            note_response_status(resp.status_code)
            return resp
        except (httpx.TimeoutException, httpx.ProxyError, httpx.TransportError) as e:
            last_exc = e
            if isinstance(e, httpx.ProxyError):
                cool_down_proxy(proxy, 30.0)
                proxy = _current_proxy_url()
            await asyncio.sleep(_RETRY_SLEEP * attempt)
    if last_exc:
        raise last_exc
    raise httpx.RequestError(f'http_post failed after {_MAX_HTTP_RETRIES} attempts')


def _rotate_to_next_proxy(reason: str) -> bool:
    global _proxy_index, _last_switch_ts, _rotating
    with _proxy_lock:
        if not _USE_PROXIES or not _proxy_pool:
            return False
        now = time.time()
        if _rotating:
            return False
        if now - _last_switch_ts < _PROXY_SWITCH_COOLDOWN:
            return False
        _rotating = True
        _proxy_hold.clear()
    try:
        with _proxy_lock:
            old = _proxy_pool[_proxy_index % len(_proxy_pool)]
            cool_down_proxy(
                old,
                _COOLDOWN_RATE_LIMITED if reason in ('429', '400') else _COOLDOWN_UNAVAILABLE,
            )
            _proxy_index = (_proxy_index + 1) % len(_proxy_pool)
            new = _proxy_pool[_proxy_index]
            _last_switch_ts = time.time()
        print_warning(f'Proxy blocked ({reason}) â rotating â¦{old[-28:]} â â¦{new[-28:]}')
        time.sleep(0.25)
        return True
    finally:
        with _proxy_lock:
            _rotating = False
            _proxy_hold.set()


def handle_blocked_status(status_code: int) -> None:
    global _prompt_pending
    if status_code not in _BLOCKED_STATUS:
        return
    if _USE_PROXIES:
        if _rotate_to_next_proxy(str(status_code)):
            return
        wait_if_held()
        return
    if not proxies_available():
        return
    with _prompt_lock:
        if _prompt_pending:
            return
        _prompt_pending = True
        _proxy_hold.clear()
        print_warning(f'Direct connection blocked ({status_code}). Proxies available â waiting for choiceâ¦')


def resolve_proxy_prompt(enable: bool) -> None:
    global _prompt_pending
    with _prompt_lock:
        if enable:
            set_proxy_mode(True)
            print_warning('Switched to Proxy mode mid-run.')
        else:
            print_warning('Continuing on Direct connection.')
        _prompt_pending = False
        _proxy_hold.set()


def note_response_status(status_code: int) -> None:
    if status_code in _BLOCKED_STATUS:
        handle_blocked_status(status_code)



def ensure_login_config() -> bool:
    global REMOTE_VERSION, RELEASE_VERSION
    if REMOTE_VERSION and RELEASE_VERSION:
        return True
    print_warning('server_url / release_version missing â refetchingâ¦')
    CLIENT_VERSION, REMOTE_VERSION, RELEASE_VERSION = AutoUpdate()
    if not CLIENT_VERSION or not REMOTE_VERSION or not RELEASE_VERSION:
        print_warning('AutoUpdate failed  - cannot continue without client_version / remote_version / release_version')
        return False
    return True

_SUBSCRIPT_MAP = {str(d): c for d, c in zip('0123456789', 'ââââââââââ')}
_NAME_MAX_LEN = 12

def _generate_suffix_digits(length: int = 6) -> str:
    length = max(1, min(int(length), 12))
    return f'{random.randint(0, 10 ** length - 1):0{length}d}'

def generate_random_name(base_name: str, suffix_digits: str | None = None) -> str:
    prefix = (base_name or 'FF').strip()
    if not prefix:
        prefix = 'FF'
    if len(prefix) >= _NAME_MAX_LEN:
        return prefix[:_NAME_MAX_LEN]
    remaining = _NAME_MAX_LEN - len(prefix)
    if suffix_digits:
        digits = ''.join(c for c in suffix_digits if c.isdigit())
    else:
        digits = ''
    if len(digits) < remaining:
        digits = _generate_suffix_digits(remaining)
    else:
        digits = digits[:remaining]
    subscript = ''.join(_SUBSCRIPT_MAP[d] for d in digits)
    return f'{prefix}{subscript}'
    
def generate_custom_password(prefix: str, suffix_digits: str) -> str:
    chars = string.ascii_uppercase + string.digits
    rc_alpha = ''.join((random.choice(chars) for _ in range(10)))
    rc_beta = ''.join((random.choice(chars) for _ in range(5)))
    return f'{prefix}_{rc_alpha}_{rc_beta}'

def generate_legacy_password() -> str:
    return secrets.token_hex(32).upper()
    
def smart_delay(low: float=0.2, high: float=0.5) -> None:
    if settings.EXIT_FLAG:
        return
    time.sleep(random.uniform(low, high))

def _encode_open_id(original: str) -> dict[str, str]:
    keystream = [48, 48, 48, 50, 48, 49, 55, 48, 48, 48, 48, 48, 50, 48, 49, 55, 48, 48, 48, 48, 48, 50, 48, 49, 55, 48, 48, 48, 48, 48, 50, 48]
    encoded = ''.join((chr(ord(c) ^ keystream[i % len(keystream)]) for i, c in enumerate(original)))
    return {'open_id': original, 'field_14': encoded}

def _to_unicode_escaped(s: str) -> str:
    return ''.join((c if 32 <= ord(c) <= 126 else f'\\u{ord(c):04x}' for c in s))

def decode_jwt_token(jwt_token: str) -> str:
    try:
        parts = jwt_token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            data = json.loads(base64.urlsafe_b64decode(payload))
            account_id = data.get('account_id') or data.get('external_id')
            if account_id:
                return str(account_id)
    except Exception as e:
        print_warning(f'JWT decode failed: {e}')
    return 'N/A'


RANGES = {
    "IND": ("IN", "117.192.0.0/14"),
    "ID":  ("ID", "36.64.0.0/10"),
    "TH":  ("TH", "171.96.0.0/13"),
    "VN":  ("VN", "14.160.0.0/11"),
    "SG":  ("SG", "118.189.0.0/16"),
    "BR":  ("BR", "177.0.0.0/8"),
    "BD":  ("BD", "114.130.0.0/16"),
    "PK":  ("PK", "39.32.0.0/11"),
    "TW":  ("TW", "1.160.0.0/12"),
    "ME":  ("SA", "37.224.0.0/12"),
    "EU":  ("DE", "46.0.0.0/8"),
    "NA":  ("US", "8.0.0.0/8"),
    "US":  ("US", "8.0.0.0/8"),
    "SAC": ("AR", "181.0.0.0/12"),
    "CIS":  ("RU", "5.0.0.0/11"),
}

def get_ip_and_country(region: str):
    region = region.upper()
    data = RANGES.get(region)
    if not data:
        raise ValueError(f"Unknown region. Use one of: {', '.join(RANGES)}")
    
    country, cidr = data
    net = ipaddress.ip_network(cidr)
    ip = str(net[random.randint(1, net.num_addresses - 2)])
    
    return ip, country

def generate_device_id(prefix: str = "02") -> str:
  random_uuid = uuid.uuid4()
  return f"{prefix}-{random_uuid}"
    
def _sign_body(body):
    return hmac.new(CLIENT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    

async def register_guest_account(region: str, password_prefix: str, suffix_digits: str) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None

    try:
        password = generate_custom_password(password_prefix, suffix_digits)

        body = json.dumps({
            "app_id": 100067,
            "client_type": 2,
            "password": password,
            "source": 2,
        }, separators=(",", ":"))
        hdrs = {
            "User-Agent": f"GarenaMSDK/4.0.44(ASUS_AI2501_B ;Android 12;en;US;app {CLIENT_VERSION} {CLIENT_VERSION_CODE};)",
            "Authorization": "Signature " + _sign_body(body),
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Length": str(len(body)),
        }

        response = None
        
        async with httpx.AsyncClient(verify=False, timeout=15.0, http2=False) as c:
            response = await asyncio.wait_for(
                c.post(OAUTH_REGISTER_URL, content=body.encode("utf-8"), headers=hdrs),
                timeout=20.0,
            )

        note_response_status(response.status_code)

        if response is None or response.status_code in (400, 403, 429):
            print_warning(
                f'Guest register v2 blocked ({getattr(response, "status_code", "?")}). Cooling Down...'
            )
            smart_delay()
            return None

        response.raise_for_status()

        body = response.json()
        data = body.get('data', body)

        if body.get('code', 0) == 0 and ('uid' in data or 'uid' in body):
            uid = data.get('uid') or body.get('uid')
            return {'uid': uid, 'password': password}

        return None

    except Exception as e:
        print_warning(f'Guest registration failed: {e}')
        smart_delay()
        return None


async def grant_oauth_token(uid: str, password: str) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None
    try:
    
        body = json.dumps({
            "client_id": 100067,
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_type": 2,
            "device_id": generate_device_id(),
            "password": password,
            "response_type": "token",
            "uid": int(uid),
        }, separators=(",", ":"))
        
        hdrs = {
            "Host": "ffmconnect.live.gop.garenanow.com",
            "User-Agent": f"GarenaMSDK/4.0.44(ASUS_AI2501_B ;Android 12;en;US;app {CLIENT_VERSION} {CLIENT_VERSION_CODE};)",
            "Connection": "Keep-Alive",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Content-Length": str(len(body)),
        }

        for attempt in range(3):
            try:
                print_info(f"[OAUTH] {uid} attempt {attempt+1}")
                async with httpx.AsyncClient(
                    verify=False,
                    timeout=httpx.Timeout(12.0, connect=8.0, read=12.0, write=12.0),
                    http2=False,
                ) as c:
                    r = await asyncio.wait_for(
                        c.post(OAUTH_TOKEN_URL, content=body.encode("utf-8"), headers=hdrs),
                        timeout=15.0,
                    )
                print_info(f"[OAUTH] {uid} status={r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    d = j.get("data") or j
                    oid = d.get("open_id")
                    at = d.get("access_token")
                    pf = d.get("platform", 4)
                    if oid and at:
                        field_data = _encode_open_id(str(oid))
                        return {
                            'open_id': str(oid),
                            'access_token': at,
                            'platform': pf,
                            'field': field_data['field_14'].encode('utf-8')
                        }
                    print_warning(f"[OAUTH] {uid} 200 missing fields: {list(d.keys())}")

                else:
                    print_warning(f"[OAUTH] {uid} HTTP {r.status_code}: {r.text[:200]}")
            except asyncio.TimeoutError:
                print_warning(f"[OAUTH] {uid} attempt {attempt+1} timeout")
            except Exception as e:
                print_warning(f"[OAUTH] {uid} attempt {attempt+1} {e.__class__.__name__}: {e}")
            await asyncio.sleep(0.4)
        print_error(f"[OAUTH] {uid} all attempts failed")
        return None
    except Exception as e:
        print_warning(f'Token grant failed: {e}')
        smart_delay()
        return None


async def major_register(
    access_token: str,
    open_id: str,
    field: bytes,
    uid: str,
    password: str,
    account_name: str,
    region: str,
    suffix_digits: str,
    platform: int = 4,
    is_ghost: bool = False,
) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None
    if not ensure_login_config():
        return None
    try:

        url = f'{LOGIN_URL}/MajorRegister'
        host = LOGIN_URL.replace('https://', '')
        
        name = generate_random_name(account_name, suffix_digits)
        lang_code = 'pt' if is_ghost else settings.REGION_LANG.get(region.upper(), 'en')

        payload_fields = {
            1: name,
            2: access_token.encode(),
            3: open_id.encode(),
            5: 102000007,
            6: 4,
            7: 1,
            13: 1,
            14: field,
            15: lang_code,
            16: 2,
            17: 1,
            20: REMOTE_VERSION.encode(),
            21: 1,
            22: bytes.fromhex("47475245010101004b02000007c5c699a4c7f6e4eff5b58ba86710755a35c380869a24e1c47f19924a0f96a65ac27890cf9f2be996da4e6cc2ef99534cb7a1396170f16edb56be4a53ebd16422e40af24ae80e37aced61d3c07e7bf376f9dbf600a13e408cd0c24f5befc4446c0bbcfeacd7b65c1688f1afa1602a8667b25954f08156ae381e6908928315160e3ad5b674f2aff299c75f8525228870af1d6380d4d6b50b0de30a30de0a41bd85da7bba7a65f3254b57d7016e8c0b3522af64a38f9b3b8f7e6d847ef0d8bd282a66e7a25d0eba76b307e51c62347424be7424e3efa238a4f3c71949458e58141c8f85d922f017d392089ba7c7a44a0e9ff5bba68c63f25491f63d33a5666368ec5ee1e3ea9b3e99f1a5c2efaca9b60334ea8441fecc378d80bc175e88ce9c5d882e281292a17ffecdd86a82ae099b2b241f9e7798dc737ed8f7910e922dabdc5c588029815560f80de5a65f7fab464ad559573fa7b64ecf19958cd292af52b77c6614e3fcbf1967b468e2cd2ad673aaa5b27076f5da9ad606b77f8565a04ed0d4355b2595464fc0530367f2bf3c771e6f357ba5220c4c177f0e9927fec5c1c2cbcb5e1ddf65ea4c5f6a794331d78bfe69de07c29870a8338acee0636e3a8a218543ae536e2ea7669c27c284a896b32a6a8fc4fbf67233f5bf9de49b9a8ac5193d27e628f2a90a954145dd20cc9dadb0f1564c305a94bc1dcc77c1ccf876affdadd4a8b5d2a874781b9123ca4ce54d1d8b2bdf38ba468fff85812139b09ae2055011c2dcb522a7ec2e2e9dc5632b61beb59b167d5ed0c1a33155edece7fc3abb400927782a412e1cd25b2a100071ed2c109a740759f6b3dae159e4937bddb567537ee5c8b6a7eb71d55e9528ebbea2b172d081")
        }

        proto_bytes = build_proto_packet(payload_fields)
        encrypted_payload = aes_encrypt_hex(proto_bytes.hex())

        req_headers = {
            "Accept-Encoding": "gzip",
            "Authorization": "Bearer",
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": host,
            "ReleaseVersion": RELEASE_VERSION,
            "Content-Length": str(len(encrypted_payload)),
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA": "v1 1",
            "X-GA-SV": str(int(time.time())),
            "X-Unity-Version": "2018.4.12f1",
        }

        response = await http_post(url, headers=req_headers, content=encrypted_payload, timeout=30.0)
        note_response_status(response.status_code)
        if response.status_code != 200:
            print_warning(f'MajorRegister returned {response.status_code} - Response: {response.text[:300]}')
            console.log(f'[red]MajorRegister HTTP {response.status_code} for uid {uid}: {response.text[:200]}[/]')
            return None


        login_result = await major_login(
            uid, password, access_token, open_id, platform, region, is_ghost=is_ghost
        )
        account_id = login_result.get('account_id', 'N/A')
        jwt_token = login_result.get('jwt_token', '')

        if not await choose_newbie_choice(account_id, region, is_ghost=is_ghost):
            print_warning(f'ChooseNewbieChoice failed for Account: {uid}')

        if not await bind_region(region, jwt_token, is_ghost=is_ghost):
            print_warning(f'Region Binding failed for Account: {uid}')

        final_login = await major_login(
            uid, password, access_token, open_id, platform, region,
            is_ghost=is_ghost, auth_jwt=jwt_token or None,
        )
        final_jwt = final_login.get('jwt_token', '')
        if final_jwt:
            jwt_token = final_jwt
            if final_login.get('account_id') and final_login.get('account_id') != 'N/A':
                account_id = final_login.get('account_id')

        result = {
            'uid': uid,
            'password': password,
            'name': name,
            'region': 'GHOST' if is_ghost else region,
            'status': 'success',
            'account_id': account_id,
            'jwt_token': jwt_token,
            'session_key': final_login.get('session_key'),
            'session_iv': final_login.get('session_iv'),
            'session_ts': final_login.get('session_ts'),
            'login_payload': final_login.get('login_payload'),
            'client_base_url': final_login.get('client_base_url'),
            'activated': False,
        }

        if getattr(settings, 'ACTIVATE_ON_RUN', False) and jwt_token:
            try:
                ok = await activate_account_async(result, region=region)
                result['activated'] = bool(ok)
                if ok:
                    print_success(f'Activated {uid} (TCP session up)')
                else:
                    debug_log(f'Activation skipped/failed for {uid}')
            except Exception as act_err:
                debug_log(f'Activation failed for {uid}: {act_err}')

        return result
    except Exception as e:
        print_warning(f'MajorRegister error: {e}')
        smart_delay()
        return None


async def major_login(
    uid: str,
    password: str,
    access_token: str,
    open_id: str,
    platform: int,
    region: str,
    is_ghost: bool = False,
    auth_jwt: str | None = None,
) -> dict:
    if not ensure_login_config():
        return {'account_id': 'N/A', 'jwt_token': ''}
    try:
        ip, country = get_ip_and_country(region)
        avail = random.randint(26000, 30000)
        platform_val = platform if platform is not None else 4

        fields = {
            3: str(datetime.now())[:-7],
            4: "free fire",
            5: 1 if str(platform_val) in ["1", "4"] else int(platform_val),
            7: REMOTE_VERSION,
            8: "Android OS 13 / API-33 (TP1A.220624.014)",
            9: "Handheld",
            10: "Singtel",
            11: "WIFI",
            12: 1280,
            13: 720,
            14: "240",
            15: "x86-64 SSE3 SSE4.1 SSE4.2 AVX AVX2 | 2400 | 4",
            16: 7597,
            17: "Adreno (TM) 730",
            18: "OpenGL ES 3.2",
            19: "Google|6baabf16-70c8-4a1e-bc0f-a92b01df69f0",
            20: str(ip),
            21: "en",
            22: str(open_id),
            23: str(platform_val),
            24: "Handheld",
            25: "OnePlus CPH2411",
            26: str(country),
            29: str(access_token),
            30: 1,
            41: "Singtel",
            42: "WIFI",
            57: "1ac4b80ecf0478a44203bf8fac6120f5",
            60: 30000,
            61: random.randint(10000, 20000),
            62: random.randint(4000, 6000),
            64: avail,
            65: 34308,
            66: avail,
            67: 34308,
            73: 3,
            74: "/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/lib/arm",
            76: 2,
            77: "428775ab8c8845bd341b5357ec61d15e|/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/base.apk",
            78: 2,
            79: 1,
            81: "32",
            83: CLIENT_VERSION_CODE,
            86: "OpenGLES2",
            87: 4095,
            88: int(platform_val),
            92: random.randint(10000, 13000),
            93: "android_max",
            94: "KqsHT2gyPt7vUCc9SCjv2ioi3WEZSEL86ErvXB38suVVK/Z4IVt78ESl/r2S15C1pqu/j6ZmgFL7HbwoFiiVconX08ooKiisQffvEAPCo/C+Lahr",
            96: "{\"cur_rate\":null,\"support_etc2\":true}",
            97: "1",
            98: "1",
            99: str(platform_val),
            100: str(platform_val),
            102: {},
            104: 77149,
            105: 1,
            106: "https://dl.cdn.freefiremobile.com/live/ABHotUpdates/|https://dl-core.cdn.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462",
            107: "c8e41b7a93f02d56e1a94c7b8203f5d1",
        }

        proto_bytes = build_proto_packet(fields)
        encrypted_payload = aes_encrypt_hex(proto_bytes.hex())

        url = f'{LOGIN_URL}/MajorLogin'
        host = LOGIN_URL.replace('https://', '')
        
        auth_value = f"Bearer {auth_jwt}" if auth_jwt else "Bearer"
        req_headers = {
            "Accept-Encoding": "gzip",
            "Authorization": auth_value,
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": host,
            "ReleaseVersion": RELEASE_VERSION,
            "Content-Length": str(len(encrypted_payload)),
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA": "v1 1",
            "X-GA-SV": str(int(time.time())),
            "X-Unity-Version": "2018.4.12f1",
        }

        response = await http_post(url, headers=req_headers, content=encrypted_payload, timeout=30.0)
        if response.status_code == 200 and len(response.content) > 10:
            raw = response.content
            body = normalize_login_response(raw)
            jwt_token = ''
            try:
                text = body.decode('utf-8', errors='ignore')
            except Exception:
                text = ''
            if 'eyJ' not in text:
                try:
                    text = response.text
                except Exception:
                    text = raw.decode('utf-8', errors='ignore')
            jwt_start = text.find('eyJ')
            if jwt_start != -1:
                jwt_token = text[jwt_start:]
                second_dot = jwt_token.find('.', jwt_token.find('.') + 1)
                if second_dot != -1:
                    jwt_token = jwt_token[:second_dot + 44]
            session_key, session_iv, session_ts = extract_session_secrets(body)
            client_base_url = extract_client_base_url(body)
            account_id = decode_jwt_token(jwt_token) if jwt_token else 'N/A'
            return {
                'account_id': account_id,
                'jwt_token': jwt_token or '',
                'session_key': session_key,
                'session_iv': session_iv,
                'session_ts': session_ts,
                'login_payload': encrypted_payload,
                'client_base_url': client_base_url,
            }
        return {'account_id': 'N/A', 'jwt_token': ''}
    except Exception as e:
        print_warning(f'MajorLogin failed: {e}')
        return {'account_id': 'N/A', 'jwt_token': ''}


_active_sockets: list = []
_active_sockets_lock = threading.Lock()


def _read_varint(buf: bytes, idx: int) -> tuple[int, int]:
    result = shift = 0
    while idx < len(buf):
        b = buf[idx]
        idx += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
        if shift > 70:
            break
    return result, idx


def parse_protobuf_fields(data: bytes) -> dict:
    fields: dict = {}
    i = 0
    n = len(data)
    while i < n:
        try:
            key, i = _read_varint(data, i)
        except Exception:
            break
        field_no = key >> 3
        wire = key & 7
        if wire == 0:
            val, i = _read_varint(data, i)
            fields[field_no] = val
        elif wire == 2:
            length, i = _read_varint(data, i)
            if i + length > n:
                break
            fields[field_no] = data[i:i + length]
            i += length
        elif wire == 5:
            i += 4
        elif wire == 1:
            i += 8
        else:
            break
    return fields


def _describe_proto_fields(fields: dict, depth: int = 0) -> str:
    parts = []
    for k, v in sorted(fields.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
        if isinstance(v, bytes):
            preview = v[:24].hex()
            extra = f'len={len(v)} hex={preview}{"â¦" if len(v) > 24 else ""}'
            try:
                s = v.decode('utf-8')
                if s.isprintable() and len(s) < 80:
                    extra += f' str={s!r}'
            except Exception:
                pass
            parts.append(f'{"  "*depth}{k}: bytes({extra})')
        elif isinstance(v, int):
            parts.append(f'{"  "*depth}{k}: varint={v}')
        else:
            parts.append(f'{"  "*depth}{k}: {type(v).__name__}={v!r}'[:120])
    return '\n'.join(parts)


def extract_session_secrets(raw: bytes) -> tuple[bytes | None, bytes | None, int | None]:
    fields = parse_protobuf_fields(raw)
    ts = fields.get(21)
    key = fields.get(22)
    iv = fields.get(23)
    if isinstance(key, bytes) and isinstance(iv, bytes) and ts is not None:
        return key, iv, int(ts) if not isinstance(ts, int) else ts

    for val in fields.values():
        if not isinstance(val, bytes) or len(val) < 8:
            continue
        nested = parse_protobuf_fields(val)
        ts = nested.get(21)
        key = nested.get(22)
        iv = nested.get(23)
        if isinstance(key, bytes) and isinstance(iv, bytes) and ts is not None:
            return key, iv, int(ts) if not isinstance(ts, int) else ts
    return None, None, None


def extract_client_base_url(raw: bytes) -> str | None:
    fields = parse_protobuf_fields(raw)

    def _as_url(val) -> str | None:
        if isinstance(val, bytes):
            try:
                val = val.decode('utf-8', errors='ignore')
            except Exception:
                return None
        if not isinstance(val, str):
            return None
        val = val.strip().rstrip('/')
        if val.startswith('http://') or val.startswith('https://'):
            return val
        return None

    url = _as_url(fields.get(10))
    if url:
        return url

    for val in fields.values():
        if not isinstance(val, bytes):
            continue
        nested = parse_protobuf_fields(val)
        url = _as_url(nested.get(10))
        if url:
            return url

        for nv in nested.values():
            url = _as_url(nv)
            if url and 'client' in url:
                return url
    return None


def aes_decrypt_hex(hex_payload: str, key: bytes, iv: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(bytes.fromhex(hex_payload)), AES.block_size)


def encode_account_hex(account_id: int | str) -> str:
    try:
        value = int(account_id)
    except (TypeError, ValueError):
        return ''
    return format(value, 'x')


def build_tcp_auth_packet(
    account_id: str,
    jwt_token: str,
    session_key: bytes,
    session_iv: bytes,
    session_ts: int,
) -> bytes | None:

    try:
        acc_hex = encode_account_hex(account_id)
        if not acc_hex:
            debug_log(f'0115 build: bad account_id={account_id!r}')
            return None
        if len(acc_hex) > 16:
            debug_log(f'0115 build: account hex too long ({len(acc_hex)}): {acc_hex}')
            return None

        prefix = '0' * (16 - len(acc_hex))

        jwt_bytes = jwt_token.encode('utf-8')
        encrypted = AES.new(session_key, AES.MODE_CBC, session_iv).encrypt(
            pad(jwt_bytes, 16)
        ).hex()

        body_len_hex = format(len(encrypted) // 2, 'x')
        ts_hex = format(int(session_ts), 'x')
        header = f'0115{prefix}{acc_hex}{ts_hex}00000{body_len_hex}'

        packet_hex = header + encrypted
        if len(packet_hex) % 2:
            packet_hex = '0' + packet_hex
            debug_log(f'0115 build: odd hex length, left-padded')

        packet = bytes.fromhex(packet_hex)
        debug_log(
            f'0115 build ok: acc={prefix}{acc_hex} ts={ts_hex} '
            f'body_len={body_len_hex} packet_len={len(packet)}'
        )
        return packet
    except Exception as e:
        debug_log('0115 build failed', exc=e)
        return None





def _parse_host_port(val) -> tuple[str | None, int | None]:
    if isinstance(val, bytes):
        try:
            val = val.decode('utf-8', errors='ignore')
        except Exception:
            return None, None
    if not isinstance(val, str) or ':' not in val:
        return None, None
        
    val = val.strip().strip('\x00')

    for token in val.replace(',', ' ').split():
        if ':' not in token:
            continue
        host, _, port_s = token.rpartition(':')
        host = host.strip().strip('[]')
        try:
            port = int(port_s.strip())
        except ValueError:
            continue
        if host and 1 <= port <= 65535:
            return host, port
    return None, None


def _collect_endpoints_from_fields(fields: dict) -> list[tuple[str, int, int]]:
    found: list[tuple[str, int, int]] = []

    def _consider(field_no, val):
        ip, port = _parse_host_port(val)
        if ip and port:
            found.append((ip, port, int(field_no) if str(field_no).isdigit() else -1))
            return
        if isinstance(val, bytes) and len(val) >= 8:
            try:
                nested = parse_protobuf_fields(val)
            except Exception:
                return
            for nk, nv in nested.items():
                ip, port = _parse_host_port(nv)
                if ip and port:
                    found.append((ip, port, int(field_no) if str(field_no).isdigit() else -1))

    for k, v in fields.items():
        _consider(k, v)
    return found


def parse_login_data_endpoints(raw: bytes) -> tuple[str | None, int | None, str | None, int | None]:
    debug_log(f'GetLoginData raw len={len(raw)} hex stream:\n{raw.hex()}')
    body = normalize_login_response(raw)
    if body is not raw:
        debug_log(f'GetLoginData normalized len={len(body)} hex stream:\n{body.hex()}')
    fields = parse_protobuf_fields(body)
    debug_log(f'GetLoginData proto fields: {sorted(fields.keys())}')
    debug_log(f'GetLoginData proto dump:\n{_describe_proto_fields(fields)}')

    chat_ip = chat_port = game_ip = game_port = None

    ip, port = _parse_host_port(fields.get(32))
    if ip:
        chat_ip, chat_port = ip, port
    ip, port = _parse_host_port(fields.get(14))
    if ip:
        game_ip, game_port = ip, port

    all_eps = _collect_endpoints_from_fields(fields)
    debug_log(f'GetLoginData addresses found: {all_eps}')

    if not chat_ip or not game_ip:
        for ip, port, fno in all_eps:
            if fno == 32 and not chat_ip:
                chat_ip, chat_port = ip, port
            elif fno == 14 and not game_ip:
                game_ip, game_port = ip, port

    if not chat_ip or not game_ip:
        unused = [(ip, port) for ip, port, _ in all_eps if (ip, port) not in {(chat_ip, chat_port), (game_ip, game_port)}]
        if not chat_ip and unused:
            chat_ip, chat_port = unused.pop(0)
        if not game_ip and unused:
            game_ip, game_port = unused.pop(0)
        if chat_ip and not game_ip:
            game_ip, game_port = chat_ip, chat_port
            debug_log('GetLoginData: only one address â using it for both chat and game')
        elif game_ip and not chat_ip:
            chat_ip, chat_port = game_ip, game_port
            debug_log('GetLoginData: only one address â using it for both chat and game')

    return chat_ip, chat_port, game_ip, game_port


async def fetch_game_endpoints(
    jwt_token: str,
    login_payload: bytes,
    client_base_url: str,
) -> tuple[str | None, int | None, str | None, int | None]:

    base = (client_base_url or '').rstrip('/')
    if not base.startswith('http'):
        return None, None, None, None
    from urllib.parse import urlparse
    host = urlparse(base).netloc or base.replace('https://', '').replace('http://', '')
    url = f'{base}/GetLoginData'
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'X-Unity-Version': '2018.4.12f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': RELEASE_VERSION or 'OB55',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
        'Host': host,
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
    }
    try:
        resp = await http_post(url, headers=headers, content=login_payload, timeout=20.0)
        debug_log(f'GetLoginData HTTP {resp.status_code} len={len(resp.content)}')
        if resp.status_code != 200:
            debug_log(f'GetLoginData body preview: {resp.content[:200]!r}')
            return None, None, None, None
        return parse_login_data_endpoints(resp.content)
    except Exception as e:
        debug_log('GetLoginData failed', exc=e)
        return None, None, None, None



def establish_tcp_session(
    auth_packet: bytes,
    chat_ip: str,
    chat_port: int,
    game_ip: str | None = None,
    game_port: int | None = None,
    hold: bool = True,
) -> bool:

    sock = None
    try:
        sock = socket.create_connection((chat_ip, int(chat_port)), timeout=8)
        sock.sendall(auth_packet)
        sock.settimeout(3.0)
        try:
            _ = sock.recv(4096)
        except socket.timeout:
            pass
        if game_ip and game_port:
            try:
                sock2 = socket.create_connection((game_ip, int(game_port)), timeout=8)
                sock2.sendall(auth_packet)
                sock2.settimeout(2.0)
                try:
                    sock2.recv(2048)
                except socket.timeout:
                    pass
                if hold:
                    with _active_sockets_lock:
                        _active_sockets.append(sock2)
                else:
                    sock2.close()
            except Exception:
                pass
        if hold:
            with _active_sockets_lock:
                _active_sockets.append(sock)

            def _keep(s=sock):
                try:
                    s.settimeout(30.0)
                    while True:
                        data = s.recv(8192)
                        if not data:
                            break
                except Exception:
                    pass
            threading.Thread(target=_keep, daemon=True, name='tcp-keep').start()
        else:
            sock.close()
        return True
    except Exception as e:
        try:
            if sock:
                sock.close()
        except Exception:
            pass
        raise e


async def _activate_account_once(account: dict, region: str | None = None) -> bool:
    uid = account.get('uid')
    jwt_token = account.get('jwt_token') or account.get('jwt') or ''
    account_id = account.get('account_id') or 'N/A'
    session_key = account.get('session_key')
    session_iv = account.get('session_iv')
    session_ts = account.get('session_ts')
    login_payload = account.get('login_payload')
    region = region or account.get('region') or 'IND'

    if not jwt_token:
        debug_log(f'[{uid}] activate_async: no jwt')
        return False

    if not (session_key and session_iv and session_ts and login_payload):
        debug_log(
            f'[{uid}] activate_async: missing secrets '
            f'key={bool(session_key)} iv={bool(session_iv)} ts={session_ts} payload={bool(login_payload)}'
        )
        return False

    client_base_url = account.get('client_base_url') or ''
    if not client_base_url:
        debug_log(f'[{uid}] activate_async: no client_base_url from MajorLogin field 10')
        return False
    chat_ip, chat_port, game_ip, game_port = await fetch_game_endpoints(
        jwt_token, login_payload, client_base_url,
    )
    if not chat_ip or not chat_port:
        debug_log(f'[{uid}] activate_async: no endpoints')
        return False

    packet = build_tcp_auth_packet(
        account_id, jwt_token, session_key, session_iv, int(session_ts),
    )
    if not packet:
        debug_log(f'[{uid}] activate_async: auth packet build failed')
        return False

    try:
        ok = await asyncio.to_thread(
            establish_tcp_session, packet, chat_ip, chat_port, game_ip, game_port, True,
        )
    except Exception as e:
        debug_log(f'[{uid}] activate_async tcp', exc=e)
        return False
    return bool(ok)


async def activate_account_async(account: dict, region: str | None = None) -> bool:
    uid = account.get('uid')
    max_attempts = int(getattr(settings, 'ACTIVATE_MAX_ATTEMPTS', 3) or 3)
    cooldowns = tuple(getattr(settings, 'ACTIVATE_COOLDOWNS', (1.5, 3.0, 6.0)) or (1.5, 3.0, 6.0))

    for attempt in range(1, max_attempts + 1):
        debug_log(f'[{uid}] activation attempt {attempt}/{max_attempts}')
        try:
            ok = await _activate_account_once(account, region=region)
        except Exception as e:
            debug_log(f'[{uid}] activation attempt {attempt} crashed', exc=e)
            ok = False
        if ok:
            with settings.LOCK:
                settings.ACTIVATED_COUNTER = getattr(settings, 'ACTIVATED_COUNTER', 0) + 1
            debug_log(f'[{uid}] activation succeeded on attempt {attempt}')
            return True
        if attempt < max_attempts:
            delay = cooldowns[min(attempt - 1, len(cooldowns) - 1)]
            debug_log(f'[{uid}] activation failed attempt {attempt}/{max_attempts} â cooldown {delay}s')
            await asyncio.sleep(delay)

    debug_log(f'[{uid}] activation failed after {max_attempts} attempts')
    return False


def oauth_grant_sync(uid: str, password: str, max_retries: int = 5) -> dict | None:
    url = OAUTH_TOKEN_URL
    body = json.dumps({
        'client_id': 100067,
        'client_secret': CLIENT_SECRET,
        'client_type': 2,
        'device_id': generate_device_id(),
        'password': password,
        'response_type': 'token',
        'uid': int(uid) if str(uid).isdigit() else uid,
    }, separators=(',', ':'))
    headers = {
        'User-Agent': f'GarenaMSDK/4.0.44(ASUS_AI2501_B ;Android 12;en;US;app {CLIENT_VERSION or "2.132.1"} {CLIENT_VERSION_CODE};)',
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
        'Connection': 'Keep-Alive',
    }
    for attempt in range(max_retries):
        try:
            r = httpx.post(url, content=body.encode(), headers=headers, verify=False, timeout=12.0)
            if r.status_code == 429:
                wait = min(2 ** attempt, 32)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                time.sleep(0.4 * (attempt + 1))
                continue
            data = r.json()
            d = data.get('data') or data
            if d.get('open_id') and d.get('access_token'):
                return {
                    'open_id': str(d['open_id']),
                    'access_token': d['access_token'],
                    'platform': d.get('platform', 4),
                }
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    return None


def major_login_sync(uid: str, password: str, access_token: str, open_id: str, region: str) -> dict:
    if not ensure_login_config():
        return {}
    try:
        ip, country = get_ip_and_country(region if region != 'GHOST' else 'BR')
        avail = random.randint(26000, 30000)
        platform_val = 4
        fields = {
            3: str(datetime.now())[:-7],
            4: 'free fire',
            5: 1,
            7: REMOTE_VERSION,
            8: 'Android OS 13 / API-33 (TP1A.220624.014)',
            9: 'Handheld',
            10: 'Singtel',
            11: 'WIFI',
            12: 1280,
            13: 720,
            14: '240',
            15: 'x86-64 SSE3 SSE4.1 SSE4.2 AVX AVX2 | 2400 | 4',
            16: 7597,
            17: 'Adreno (TM) 730',
            18: 'OpenGL ES 3.2',
            19: f'Google|{uuid.uuid4()}',
            20: str(ip),
            21: 'en',
            22: str(open_id),
            23: str(platform_val),
            24: 'Handheld',
            25: 'OnePlus CPH2411',
            26: str(country),
            29: str(access_token),
            30: 1,
            41: 'Singtel',
            42: 'WIFI',
            57: '1ac4b80ecf0478a44203bf8fac6120f5',
            60: 30000,
            61: random.randint(10000, 20000),
            62: random.randint(4000, 6000),
            64: avail,
            65: 34308,
            66: avail,
            67: 34308,
            73: 3,
            74: '/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/lib/arm',
            76: 2,
            77: '428775ab8c8845bd341b5357ec61d15e|/data/app/~~iw-K-GR3srU7dLE-UxJ4bg==/com.dts.freefiremax-kbPhw3SUYautW0I_oayB_A==/base.apk',
            78: 2,
            79: 1,
            81: '32',
            83: CLIENT_VERSION_CODE,
            86: 'OpenGLES2',
            87: 4095,
            88: int(platform_val),
            92: random.randint(10000, 13000),
            93: 'android_max',
            94: 'KqsHT2gyPt7vUCc9SCjv2ioi3WEZSEL86ErvXB38suVVK/Z4IVt78ESl/r2S15C1pqu/j6ZmgFL7HbwoFiiVconX08ooKiisQffvEAPCo/C+Lahr',
            96: '{"cur_rate":null,"support_etc2":true}',
            97: '1',
            98: '1',
            99: str(platform_val),
            100: str(platform_val),
            102: {},
            104: 77149,
            105: 1,
            106: 'https://dl.cdn.freefiremobile.com/live/ABHotUpdates/|https://dl-core.cdn.freefiremobile.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462',
            107: 'c8e41b7a93f02d56e1a94c7b8203f5d1',
        }
        proto_bytes = build_proto_packet(fields)
        encrypted_payload = aes_encrypt_hex(proto_bytes.hex())
        url = f'{LOGIN_URL}/MajorLogin'
        host = LOGIN_URL.replace('https://', '')
        headers = {
            'Accept-Encoding': 'gzip',
            'Authorization': 'Bearer',
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': host,
            'ReleaseVersion': RELEASE_VERSION,
            'Content-Length': str(len(encrypted_payload)),
            'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'X-GA': 'v1 1',
            'X-GA-SV': str(int(time.time())),
            'X-Unity-Version': '2018.4.12f1',
        }
        with httpx.Client(verify=False, timeout=20.0) as c:
            resp = c.post(url, headers=headers, content=encrypted_payload)
        debug_log(
            f'[{uid}] MajorLogin HTTP {resp.status_code} '
            f'len={len(resp.content)} ctype={resp.headers.get("content-type", "?")}'
        )
        if resp.status_code != 200:
            body_preview = resp.content[:300]
            try:
                body_txt = resp.text[:300]
            except Exception:
                body_txt = repr(body_preview)
            debug_log(f'[{uid}] MajorLogin non-200 body: {body_txt}')
            return {}
        raw = resp.content
        body = normalize_login_response(raw)
        if body is not raw:
            debug_log(f'[{uid}] MajorLogin body normalized {len(raw)} â {len(body)} bytes')
        text = body.decode('utf-8', errors='ignore')
        if 'eyJ' not in text:
            text = raw.decode('utf-8', errors='ignore')
        jwt_token = ''
        jwt_start = text.find('eyJ')
        if jwt_start != -1:
            jwt_token = text[jwt_start:]
            second_dot = jwt_token.find('.', jwt_token.find('.') + 1)
            if second_dot != -1:
                jwt_token = jwt_token[:second_dot + 44]
        try:
            fields = parse_protobuf_fields(body)
            debug_log(f'[{uid}] MajorLogin proto top-level fields: {sorted(fields.keys())}')
            debug_log(f'[{uid}] MajorLogin proto dump:\n{_describe_proto_fields(fields)}')
        except Exception as parse_err:
            debug_log(f'[{uid}] MajorLogin proto parse error', exc=parse_err)
            fields = {}
        session_key, session_iv, session_ts = extract_session_secrets(body)
        client_base_url = extract_client_base_url(body)
        account_id = decode_jwt_token(jwt_token) if jwt_token else 'N/A'
        debug_log(
            f'[{uid}] parsed jwt={"yes" if jwt_token else "no"} '
            f'account_id={account_id} key={bool(session_key)} iv={bool(session_iv)} '
            f'ts={session_ts} client_base={client_base_url!r}'
        )
        if not session_key or not session_iv or session_ts is None:
            debug_log(f'[{uid}] session secret extraction failed â raw head hex={raw[:64].hex()}')
        return {
            'account_id': account_id,
            'jwt_token': jwt_token,
            'session_key': session_key,
            'session_iv': session_iv,
            'session_ts': session_ts,
            'login_payload': encrypted_payload,
            'client_base_url': client_base_url,
        }
    except Exception as e:
        debug_log(f'[{uid}] MajorLogin sync exception', exc=e)
        print_warning(f'MajorLogin sync failed: {e}')
        return {}


def fetch_game_endpoints_sync(jwt_token: str, login_payload: bytes, client_base_url: str):
    base = (client_base_url or '').rstrip('/')
    if not base.startswith('http'):
        return None, None, None, None
    from urllib.parse import urlparse
    host = urlparse(base).netloc or base.replace('https://', '').replace('http://', '')
    url = f'{base}/GetLoginData'
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'X-Unity-Version': '2018.4.12f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': RELEASE_VERSION or 'OB55',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
        'Host': host,
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip',
    }
    try:
        with httpx.Client(verify=False, timeout=20.0) as c:
            resp = c.post(url, headers=headers, content=login_payload)
        debug_log(f'GetLoginData HTTP {resp.status_code} len={len(resp.content)}')
        if resp.status_code != 200:
            debug_log(f'GetLoginData body preview: {resp.content[:200]!r}')
            return None, None, None, None
        return parse_login_data_endpoints(resp.content)
    except Exception as e:
        debug_log('GetLoginData sync failed', exc=e)
        return None, None, None, None



def activate_one_account(uid: str, password: str, region: str = 'IND') -> dict | None:
    try:
        debug_log(f'[{uid}] oauth grantâ¦')
        oauth = oauth_grant_sync(uid, password)
        if not oauth:
            debug_log(f'[{uid}] oauth grant failed (no open_id/access_token)')
            return None
        debug_log(f'[{uid}] oauth ok open_id={str(oauth.get("open_id", ""))[:18]}â¦')

        debug_log(f'[{uid}] major loginâ¦')
        login = major_login_sync(uid, password, oauth['access_token'], oauth['open_id'], region)
        if not login:
            debug_log(f'[{uid}] major login returned empty dict')
            return None

        jwt_token = login.get('jwt_token') or ''
        if not jwt_token:
            debug_log(f'[{uid}] major login missing jwt â cannot continue')
            return None

        if not login.get('session_key') or not login.get('session_iv') or not login.get('session_ts'):
            debug_log(
                f'[{uid}] missing session secrets '
                f'key={bool(login.get("session_key"))} iv={bool(login.get("session_iv"))} '
                f'ts={login.get("session_ts")} â TCP 0115 packet needs key/iv/ts from MajorLogin fields 21/22/23'
            )
            return None

        client_base_url = login.get('client_base_url') or ''
        if not client_base_url:
            debug_log(f'[{uid}] missing client_base_url (MajorLogin field 10)')
            return None

        debug_log(f'[{uid}] get login data via {client_base_url}â¦')
        chat_ip, chat_port, game_ip, game_port = fetch_game_endpoints_sync(
            jwt_token, login['login_payload'], client_base_url,
        )
        if not chat_ip or not chat_port:
            debug_log(f'[{uid}] endpoints missing chat={chat_ip}:{chat_port} game={game_ip}:{game_port}')
            return None
        debug_log(f'[{uid}] endpoints chat={chat_ip}:{chat_port} game={game_ip}:{game_port}')

        packet = build_tcp_auth_packet(
            login.get('account_id') or uid,
            jwt_token,
            login['session_key'],
            login['session_iv'],
            int(login['session_ts']),
        )
        if not packet:
            debug_log(f'[{uid}] failed to build 0115 auth packet')
            return None

        try:
            debug_log(f'[{uid}] tcp connectâ¦')
            establish_tcp_session(packet, chat_ip, chat_port, game_ip, game_port, hold=True)
        except Exception as e:
            debug_log(f'[{uid}] tcp error', exc=e)
            return None

        debug_log(f'[{uid}] tcp session established')
        return {
            'uid': uid,
            'password': password,
            'account_id': login.get('account_id', 'N/A'),
            'region': region,
            'jwt_token': jwt_token,
            'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except Exception as e:
        debug_log(f'[{uid}] activate_one_account crashed', exc=e)
        return None



def _list_account_json_files() -> list[str]:
    files: list[str] = []
    if os.path.exists(settings.ACCOUNTS_FOLDER):
        files.extend(
            os.path.join(settings.ACCOUNTS_FOLDER, f)
            for f in sorted(os.listdir(settings.ACCOUNTS_FOLDER))
            if f.endswith('.json')
        )
    ghost = os.path.join(settings.GHOST_ACCOUNTS_FOLDER, 'ghost.json')
    if os.path.exists(ghost):
        files.append(ghost)
    return files


def activator_flow() -> None:
    clear_screen()
    display_banner()
    files = _list_account_json_files()
    if not files:
        console.print(Panel('[yellow]No account files found.[/]', border_style='yellow', box=box.ROUNDED))
        wait_for_enter()
        return

    table = Table(box=box.ROUNDED, border_style='bright_cyan', expand=True)
    table.add_column('#', style='bold cyan', width=4, justify='right')
    table.add_column('File', style='bright_white')
    table.add_column('Accounts', style='green', justify='right')
    for i, fp in enumerate(files, 1):
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                count = len(json.load(f))
        except Exception:
            count = '?'
        table.add_row(str(i), os.path.basename(fp), str(count))
    table.add_row('0', '[yellow]â Back[/]', '')
    console.print(Panel(table, title='[bold bright_cyan]Choose account file for Activation[/]', border_style='bright_cyan', box=box.ROUNDED))

    while True:
        raw = Prompt.ask('[bold bright_cyan]File number[/]', default='1').strip()
        if raw == '0':
            return
        if raw.isdigit() and 1 <= int(raw) <= len(files):
            chosen = files[int(raw) - 1]
            break
        print_error('Invalid choice.')

    try:
        with open(chosen, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        print_error(f'Failed to load file: {e}')
        wait_for_enter()
        return

    pairs = []
    for rec in records:
        uid = str(rec.get('uid', '')).strip()
        password = str(rec.get('password', '')).strip()
        region = str(rec.get('region', 'IND')).strip() or 'IND'
        if region in ('Not Locked Yet', 'GHOST'):
            region = 'BR'
        if uid and password:
            pairs.append((uid, password, region))

    if not pairs:
        print_error('No uid/password pairs in that file.')
        wait_for_enter()
        return

    thread_count = _prompt_int('ð§µ Activation threads', min_val=1, default=min(10, len(pairs)))
    console.print()
    console.print(f'[dim]Source:[/] [cyan]{os.path.basename(chosen)}[/]  Â·  [dim]{len(pairs)} accounts[/]')
    console.print()

    spinner = ['â ', 'â ', 'â ¹', 'â ¸', 'â ¼', 'â ´', 'â ¦', 'â §', 'â ', 'â ']
    stop_spin = threading.Event()
    activated: list[dict] = []
    failed = 0
    done_count = 0
    state_lock = threading.Lock()
    ui_lock = threading.Lock()
    spin_idx = 0
    total = len(pairs)

    _CLR = '\r\x1b[2K'

    def _heading_text() -> str:
        frame = spinner[spin_idx % len(spinner)]
        with state_lock:
            d, a, f_ = done_count, len(activated), failed

        width = shutil.get_terminal_size((100, 20)).columns
        tail = f'Activating accountsâ¦ {a} ok Â· {f_} fail Â· {d}/{total}'
        max_tail = max(10, width - 20)
        if len(tail) > max_tail:
            tail = tail[:max_tail - 1] + 'â¦'
        return (
            f'  \x1b[36m{frame}\x1b[0m  '
            f'\x1b[96m\x1b[1mâï¸ SNOWFLAKE\x1b[0m  '
            f'\x1b[90m{tail}\x1b[0m'
        )

    def _redraw_heading() -> None:
        sys.stdout.write(_CLR + _heading_text())
        sys.stdout.flush()

    def _spin() -> None:
        nonlocal spin_idx
        while not stop_spin.is_set():
            spin_idx += 1
            with ui_lock:
                _redraw_heading()
            stop_spin.wait(0.08)

    def _log_status(msg: str) -> None:
        with ui_lock:
            sys.stdout.write(_CLR + msg + '\n')
            _redraw_heading()

    with ui_lock:
        _redraw_heading()

    spin_t = threading.Thread(target=_spin, daemon=True)
    spin_t.start()

    def _worker(item):
        nonlocal failed, done_count
        uid, password, region = item
        result = None
        last_err = None
        max_attempts = int(getattr(settings, 'ACTIVATE_MAX_ATTEMPTS', 3) or 3)
        cooldowns = tuple(getattr(settings, 'ACTIVATE_COOLDOWNS', (1.5, 3.0, 6.0)) or (1.5, 3.0, 6.0))
        for attempt in range(1, max_attempts + 1):
            try:
                debug_log(f'[{uid}] menu activation attempt {attempt}/{max_attempts}')
                result = activate_one_account(uid, password, region)
                if result:
                    break
                debug_log(f'[{uid}] activate_one_account returned None (attempt {attempt}/{max_attempts})')
            except Exception as e:
                last_err = e
                debug_log(f'[{uid}] activate_one_account exception', exc=e)
                result = None
            if result:
                break
            if attempt < max_attempts:
                delay = cooldowns[min(attempt - 1, len(cooldowns) - 1)]
                debug_log(f'[{uid}] cooldown {delay}s before retry')
                time.sleep(delay)
        if not result:
            debug_log(f'[{uid}] activation failed after {max_attempts} attempts')
        with state_lock:
            done_count += 1
            if result:
                activated.append(result)
                msg = f'  \x1b[32mâ\x1b[0m  {uid}  activated  (id {result.get("account_id", "?")})'
            else:
                failed += 1
                msg = f'  \x1b[31mâ\x1b[0m  {uid}  activation failed'
                if last_err:
                    debug_log(f'final error {uid}: {last_err}')
        _log_status(msg)
        return result

    try:
        with ThreadPoolExecutor(max_workers=thread_count) as pool:
            futs = [pool.submit(_worker, p) for p in pairs]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    debug_log(f'worker future error: {e}')
    finally:
        stop_spin.set()
        spin_t.join(timeout=1.0)
        with ui_lock:
            sys.stdout.write(
                _CLR +
                f'  \x1b[32mâ\x1b[0m  \x1b[96m\x1b[1mâï¸ SNOWFLAKE\x1b[0m  '
                f'\x1b[90mDone â {len(activated)} ok Â· {failed} fail Â· {done_count}/{total}\x1b[0m\n'
            )
            sys.stdout.flush()

    base = os.path.splitext(os.path.basename(chosen))[0]
    out_name = f'{base}_activated.json'
    out_path = os.path.join(os.path.dirname(chosen), out_name)
    slim = [{'uid': a['uid'], 'password': a['password']} for a in activated]
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(slim, f, indent=2, ensure_ascii=False)
        console.print(f'\n  [green]â[/]  Saved {len(slim)} activated accounts â [cyan]{out_path}[/]')
    except Exception as e:
        print_error(f'Could not save activated list: {e}')

    console.print(Panel(
        f'[green]Activated[/] {len(activated)}/{len(pairs)}   [red]Failed[/] {failed}',
        title='[bold bright_cyan]Activation complete[/]',
        border_style='bright_cyan',
        box=box.ROUNDED,
    ))
    wait_for_enter()



async def choose_newbie_choice(uid, region: str, is_ghost: bool = False) -> bool:
    try:
        url = f'{LOGIN_URL}/ChooseNewbieChoice'
        host = LOGIN_URL.replace('https://', '')

        try:
            uid_val = int(uid) if str(uid).isdigit() else uid
        except (TypeError, ValueError):
            uid_val = uid

        proto_data = build_proto_packet({1: uid_val, 2: 2, 3: 3})
        payload = bytes.fromhex(aes_encrypt_to_hex(proto_data.hex()))

        req_headers = {
            'Accept-Encoding': 'gzip',
            'Authorization': 'Bearer',
            'Connection': 'Keep-Alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': host,
            'ReleaseVersion': RELEASE_VERSION,
            'Content-Length': str(len(payload)),
            'User-Agent': 'UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'X-GA': 'v1 1',
            'X-GA-SV': str(int(time.time())),
            'X-Unity-Version': '2018.4.12f1',
        }

        response = await http_post(url, headers=req_headers, content=payload, timeout=30.0)
        note_response_status(response.status_code)
        return response.status_code == 200
    except Exception as e:
        print_warning(f'ChooseNewbieChoice failed: {e}')
        return False

async def bind_region(region: str, jwt_token: str, is_ghost: bool = False) -> bool:

    if not ensure_login_config():
        return False
    try:
        if not is_ghost:
            url = f'{LOGIN_URL}/ChooseRegion'
            host = LOGIN_URL.replace('https://', '')
        
        region_code = "RU" if region.upper() == "CIS" else region.upper()
        proto_data  = build_proto_packet({1: region_code})
        payload     = bytes.fromhex(aes_encrypt_to_hex(proto_data.hex()))

        req_headers = {
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {jwt_token}",
            "Connection": "Keep-Alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": host,
            "ReleaseVersion": RELEASE_VERSION,
            "Content-Length": str(len(payload)),
            "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            "X-GA": "v1 1",
            "X-GA-SV": str(int(time.time())),
            "X-Unity-Version": "2018.4.12f1",
        }

        response = await http_post(url, headers=req_headers, content=payload, timeout=30.0)
        note_response_status(response.status_code)
        return response.status_code == 200

    except Exception as e:
        print_warning(f"Region binding failed: {e}")
        return False
        
async def create_account(region: str, account_name: str, password_prefix: str, is_ghost: bool = False) -> Optional[dict]:
    if settings.EXIT_FLAG:
        return None
    await async_wait_if_held()
    if not ensure_login_config():
        return None
    suffix_digits = _generate_suffix_digits()
    guest = await register_guest_account(region, password_prefix, suffix_digits)
    if not guest:
        return None
    uid, password = guest['uid'], guest['password']
    oauth = await grant_oauth_token(uid, password)
    if not oauth:
        return None
    return await major_register(
        access_token=oauth['access_token'],
        open_id=oauth['open_id'],
        field=oauth['field'],
        uid=uid,
        password=password,
        account_name=account_name,
        region=region,
        suffix_digits=suffix_digits,
        platform=oauth.get('platform', 4),
        is_ghost=is_ghost,
    )


_BUF_LOCK = threading.Lock()
_WRITE_LOCK = threading.Lock()
_BUF_NORMAL: list[tuple] = []
_BUF_JWT: list[tuple] = []
_BUF_RARE: list[tuple] = []
_BUF_COUPLES: list[tuple] = []
_FLUSH_EVERY_ACCOUNTS = 40
_FLUSH_EVERY_SECONDS = 3.0
_accounts_since_flush = 0
_STOP_BG = threading.Event()
_BG_THREAD: threading.Thread | None = None
_STARTED = False

def _load_json_list(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _write_json_list(path: str, data: list) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _account_path(label: str, is_ghost: bool) -> str:
    if is_ghost:
        return os.path.join(settings.GHOST_ACCOUNTS_FOLDER, 'ghost.json')
    return os.path.join(settings.ACCOUNTS_FOLDER, f'{label}.json')

def _jwt_path(label: str, is_ghost: bool) -> str:
    if is_ghost:
        folder = getattr(settings, 'GHOST_TOKENS_FOLDER', None) or settings.GHOST_ACCOUNTS_FOLDER
        return os.path.join(folder, 'ghost_tokens.json')
    folder = getattr(settings, 'TOKENS_FOLDER', settings.ACCOUNTS_FOLDER)
    return os.path.join(folder, f'{label}_tokens.json')

def _rare_path(is_ghost: bool) -> str:
    if is_ghost:
        return os.path.join(settings.GHOST_RARE_FOLDER, 'rare.json')
    return os.path.join(settings.RARE_ACCOUNTS_FOLDER, 'rare.json')

def _couples_path(is_ghost: bool) -> str:
    if is_ghost:
        return os.path.join(settings.GHOST_COUPLES_FOLDER, 'couples.json')
    return os.path.join(settings.COUPLES_ACCOUNTS_FOLDER, 'couples.json')

def _bulk_merge(path: str, new_items: list, id_key: str='uid') -> None:
    existing = _load_json_list(path)
    seen = set()
    for item in existing:
        if isinstance(item, dict) and item.get(id_key) is not None:
            seen.add(str(item.get(id_key)))
    for item in new_items:
        if not isinstance(item, dict):
            existing.append(item)
            continue
        key = item.get(id_key)
        if key is not None and str(key) in seen:
            continue
        existing.append(item)
        if key is not None:
            seen.add(str(key))
    _write_json_list(path, existing)

def _swap_buffers() -> tuple[list, list, list, list]:
    global _accounts_since_flush
    with _BUF_LOCK:
        normals = _BUF_NORMAL[:]
        jwts = _BUF_JWT[:]
        rares = _BUF_RARE[:]
        couples = _BUF_COUPLES[:]
        _BUF_NORMAL.clear()
        _BUF_JWT.clear()
        _BUF_RARE.clear()
        _BUF_COUPLES.clear()
        _accounts_since_flush = 0
    return (normals, jwts, rares, couples)

def _write_batch(normals, jwts, rares, couples) -> None:
    if not (normals or jwts or rares or couples):
        return
    with _WRITE_LOCK:
        try:
            by_path: dict[str, list] = {}
            for account, label, is_ghost in normals:
                by_path.setdefault(_account_path(label, is_ghost), []).append(account)
            for path, items in by_path.items():
                _bulk_merge(path, items, id_key='uid')
        except Exception as e:
            print_warning(f'Bulk account save failed: {e}')
            for account, label, is_ghost in normals:
                try:
                    save_normal_account(account, label, is_ghost=is_ghost)
                except Exception as e2:
                    print_warning(f'Save account failed: {e2}')
        try:
            by_path = {}
            for account, token, label, is_ghost in jwts:
                entry = {'uid': account.get('uid'), 'account_id': account.get('account_id'), 'name': account.get('name'), 'jwt_token': token, 'region': account.get('region')}
                by_path.setdefault(_jwt_path(label, is_ghost), []).append(entry)
            for path, items in by_path.items():
                _bulk_merge(path, items, id_key='uid')
        except Exception as e:
            print_warning(f'Bulk JWT save failed: {e}')
            for account, token, label, is_ghost in jwts:
                try:
                    save_jwt_token(account, token, label, is_ghost=is_ghost)
                except Exception as e2:
                    print_warning(f'Save JWT failed: {e2}')
        for account, rtype, reason, score, is_ghost in rares:
            try:
                save_rare_account(account, rtype, reason, score, is_ghost)
            except Exception as e2:
                print_warning(f'Save rare failed: {e2}')
        for account, partner, reason, is_ghost in couples:
            try:
                save_couples_account(account, partner, reason, is_ghost)
            except Exception as e2:
                print_warning(f'Save couples failed: {e2}')

def flush_saves(timeout: float=15.0) -> None:
    normals, jwts, rares, couples = _swap_buffers()
    _write_batch(normals, jwts, rares, couples)

def _bg_flush_loop() -> None:
    while not _STOP_BG.wait(_FLUSH_EVERY_SECONDS):
        try:
            normals, jwts, rares, couples = _swap_buffers()
            if normals or jwts or rares or couples:
                _write_batch(normals, jwts, rares, couples)
        except Exception as e:
            try:
                print_warning(f'Background save error: {e}')
            except Exception:
                pass

def start_save_writer() -> None:
    global _BG_THREAD, _STARTED, _accounts_since_flush
    with _BUF_LOCK:
        _BUF_NORMAL.clear()
        _BUF_JWT.clear()
        _BUF_RARE.clear()
        _BUF_COUPLES.clear()
        _accounts_since_flush = 0
    _STOP_BG.clear()
    if _BG_THREAD is None or not _BG_THREAD.is_alive():
        _BG_THREAD = threading.Thread(target=_bg_flush_loop, name='save-bg', daemon=True)
        _BG_THREAD.start()
    _STARTED = True

def shutdown_saves() -> None:
    _STOP_BG.set()
    try:
        flush_saves()
    except Exception:
        pass

def _maybe_trigger_flush() -> None:
    global _accounts_since_flush
    with _BUF_LOCK:
        _accounts_since_flush += 1
        should = _accounts_since_flush >= _FLUSH_EVERY_ACCOUNTS
        if should:
            _accounts_since_flush = 0
    if should:
        try:
            normals, jwts, rares, couples = _swap_buffers()
            if normals or jwts or rares or couples:
                threading.Thread(target=_write_batch, args=(normals, jwts, rares, couples), daemon=True, name='save-batch').start()
        except Exception:
            pass

async def generate_single_account(region: str, account_name: str, password_prefix: str, total_accounts: int, thread_id: int, is_ghost: bool=False) -> dict | None:
    if settings.EXIT_FLAG:
        return None
    reserved = False
    try:
        with settings.LOCK:
            if settings.SUCCESS_COUNTER + settings.INFLIGHT_COUNTER >= total_accounts:
                return None
            settings.INFLIGHT_COUNTER += 1
            reserved = True
        account = await create_account(region, account_name, password_prefix, is_ghost)
        with settings.LOCK:
            if reserved:
                settings.INFLIGHT_COUNTER = max(0, settings.INFLIGHT_COUNTER - 1)
                reserved = False
            if not account:
                return None
            if settings.SUCCESS_COUNTER >= total_accounts:
                return None
            settings.SUCCESS_COUNTER += 1
            current_count = settings.SUCCESS_COUNTER
            if settings.SUCCESS_COUNTER >= total_accounts:
                settings.EXIT_FLAG = True
        account_id = account.get('account_id', 'N/A')
        jwt_token = account.get('jwt_token', '')
        account['thread_id'] = thread_id
        print_registration_status(current_count, total_accounts, account['name'], account['uid'], account['password'], account_id, region, is_ghost)
        is_rare, rarity_type, rarity_reason, rarity_score = check_account_rarity(account)
        if is_rare:
            rarity_type = rarity_type or 'RARE_ACCOUNT'
            rarity_reason = rarity_reason or 'Unknown rarity reason'
            with settings.LOCK:
                settings.RARE_COUNTER += 1
            print_rarity_found(account, rarity_type, rarity_reason, rarity_score)
            try:
                with _WRITE_LOCK:
                    save_rare_account(account, rarity_type, rarity_reason, rarity_score, is_ghost)
            except Exception as e:
                print_warning(f'Rare save failed: {e}')
                try:
                    with _BUF_LOCK:
                        _BUF_RARE.append((account, rarity_type, rarity_reason, rarity_score, is_ghost))
                except Exception:
                    pass
            update_live(rare=settings.RARE_COUNTER, render=False)
        is_couple, couple_reason, partner = check_account_couples(account, thread_id)
        if is_couple and partner:
            couple_reason = couple_reason or 'Unknown couples reason'
            with settings.LOCK:
                settings.COUPLES_COUNTER += 1
            print_couples_found(account, partner, couple_reason)
            try:
                with _WRITE_LOCK:
                    save_couples_account(account, partner, couple_reason, is_ghost)
            except Exception as e:
                print_warning(f'Couples save failed: {e}')
                try:
                    with _BUF_LOCK:
                        _BUF_COUPLES.append((account, partner, couple_reason, is_ghost))
                except Exception:
                    pass
            update_live(couples=settings.COUPLES_COUNTER, render=False)
        save_label = 'GHOST' if is_ghost else region
        with _BUF_LOCK:
            _BUF_NORMAL.append((account, save_label, is_ghost))
            if jwt_token:
                _BUF_JWT.append((account, jwt_token, save_label, is_ghost))
        _maybe_trigger_flush()
        update_live(current=current_count, render=False)
        return {'account': account}
    finally:
        if reserved:
            with settings.LOCK:
                settings.INFLIGHT_COUNTER = max(0, settings.INFLIGHT_COUNTER - 1)

async def worker(region: str, account_name: str, password_prefix: str,
                 total_accounts: int, thread_id: int, is_ghost: bool = False) -> None:
    while not settings.EXIT_FLAG:
        await async_wait_if_held()
        with settings.LOCK:
            if settings.SUCCESS_COUNTER >= total_accounts:
                break
            if settings.SUCCESS_COUNTER + settings.INFLIGHT_COUNTER >= total_accounts:
                break
        try:
            result = await generate_single_account(
                region, account_name, password_prefix,
                total_accounts, thread_id, is_ghost,
            )
        except Exception as e:
            print_warning(f'Worker exception: {e}')
            result = None

        if result is None:
            await asyncio.sleep(random.uniform(0.05, 0.12))
        else:
            await asyncio.sleep(0)
            
            
from rich import box
DEFAULT_NAME_PREFIX = 'SF'
DEFAULT_PASS_PREFIX = 'SF'
DEFAULT_REGION_CHOICE = '1'
DEFAULT_ACC_COUNT = 100
DEFAULT_RARITY_THRESHOLD = 8
DEFAULT_THREAD_COUNT = 15
recommended_threads = None

def wait_for_enter() -> None:
    try:
        Prompt.ask('\n[bold bright_cyan]â  Press Enter to continue[/]', default='')
    except KeyboardInterrupt:
        safe_exit()

def _panel(title: str, body: str, style: str='bright_blue') -> None:
    console.print(Panel(body, title=title, border_style=style, box=box.ROUNDED, padding=(0, 1)))

async def generate_accounts_flow() -> None:
    global SUCCESS_COUNTER
    clear_screen()
    display_banner()
    cpu_count = psutil.cpu_count() or 1
    recommended_threads = min(cpu_count, 3)
    regions_to_show = sorted((r for r in settings.REGION_LANG if r != 'BR'))
    region_table = Table(box=box.SIMPLE, show_header=False, pad_edge=False, expand=False)
    region_table.add_column(style='bright_white', width=4, justify='right')
    region_table.add_column(style='cyan')
    region_table.add_column(style='dim')
    for i, region in enumerate(regions_to_show, 1):
        region_table.add_row(f'{i})', region, f'({settings.REGION_LANG[region]})')
    region_table.add_row(f'{len(regions_to_show) + 1})', '[bold magenta]GHOST Mode[/]', '')
    region_table.add_row('00)', '[yellow]Back to Main Menu[/]', '')
    region_table.add_row('000)', '[red]Exit[/]', '')
    console.print(Panel(region_table, title='[bold bright_cyan]ð  Regions[/]', border_style='bright_cyan', box=box.ROUNDED))
    selected_region = ''
    is_ghost = False
    while True:
        try:
            choice = Prompt.ask('[bold bright_cyan]ð¯ Choose option[/]', default=DEFAULT_REGION_CHOICE).strip().upper()
            if choice == '00':
                return
            elif choice == '000':
                console.print('\n[bold green]ð Thanks for using SNOWFLAKE![/]')
                sys.exit(0)
            elif choice.isdigit():
                n = int(choice)
                if 1 <= n <= len(regions_to_show):
                    selected_region = regions_to_show[n - 1]
                    is_ghost = False
                    break
                elif n == len(regions_to_show) + 1:
                    selected_region = 'BR'
                    is_ghost = True
                    break
                else:
                    print_error('Invalid option.')
            elif choice in regions_to_show:
                selected_region = choice
                is_ghost = False
                break
            elif choice == 'GHOST':
                selected_region = 'BR'
                is_ghost = True
                break
            else:
                print_error('Invalid option. Please choose a valid region or number.')
        except ValueError:
            console.print('[bold red]Invalid input. Please enter a number.[/]')
        except KeyboardInterrupt:
            safe_exit()
    clear_screen()
    display_banner()
    if is_ghost:
        console.print(Panel('[bold magenta]ð Selected Mode: GHOST MODE[/]', border_style='magenta', box=box.ROUNDED))
    else:
        console.print(Panel(f'[bold cyan]ð Selected Region: {selected_region} ({settings.REGION_LANG[selected_region]})[/]', border_style='cyan', box=box.ROUNDED))
    account_count = _prompt_int('ð¯ How many accounts to generate', min_val=1, default=DEFAULT_ACC_COUNT)
    account_name = _prompt_str('ð¤ Enter account name prefix', default=DEFAULT_NAME_PREFIX)
    password_prefix = _prompt_str('ð Enter password prefix', default=DEFAULT_PASS_PREFIX)
    while True:
        try:
            raw = Prompt.ask(f'[bold bright_cyan]â­ Rarity score threshold (1â10)[/]', default=str(DEFAULT_RARITY_THRESHOLD)).strip()
            if not raw:
                rarity_threshold = DEFAULT_RARITY_THRESHOLD
            else:
                rarity_threshold = int(raw)
            if 1 <= rarity_threshold <= 10:
                settings.RARITY_SCORE_THRESHOLD = rarity_threshold
                break
            print_error('Please enter a number between 1 and 10.')
        except ValueError:
            print_error('Invalid input.')
        except KeyboardInterrupt:
            safe_exit()
    thread_count = _prompt_int(f'ð§µ Thread count (recommended: {recommended_threads})', min_val=1, default=DEFAULT_THREAD_COUNT)
    use_proxy = False
    while True:
        try:
            raw = Prompt.ask('[bold bright_cyan]ð Use proxies? (y/n)[/]', default='n').strip().lower()
            if raw in ('y', 'yes'):
                if not proxies_available():
                    print_error('Proxy list is empty. Add proxies in core/api.py (PROXY_LIST) first.')
                    continue
                use_proxy = True
                break
            if raw in ('n', 'no', ''):
                use_proxy = False
                break
            print_error('Please enter y or n.')
        except KeyboardInterrupt:
            safe_exit()
    set_proxy_mode(use_proxy)

    activate_on_run = True
    while True:
        try:
            raw = Prompt.ask(
                '[bold bright_cyan]â¡ Activate accounts on generate? (y/n)[/]',
                default='y',
            ).strip().lower()
            if raw in ('y', 'yes', ''):
                activate_on_run = True
                break
            if raw in ('n', 'no'):
                activate_on_run = False
                break
            print_error('Please enter y or n.')
        except KeyboardInterrupt:
            safe_exit()
    settings.ACTIVATE_ON_RUN = activate_on_run
    settings.ACTIVATED_COUNTER = 0

    mode_label = 'GHOST MODE' if is_ghost else selected_region
    summary_info = {'mode': mode_label, 'is_ghost': is_ghost, 'target': account_count, 'name': account_name, 'password': password_prefix, 'rarity': settings.RARITY_SCORE_THRESHOLD, 'threads': thread_count, 'connection': 'Proxy' if use_proxy else 'Direct', 'use_proxy': use_proxy, 'output': settings.ACCOUNTS_FOLDER}
    if not ensure_login_config():
        print_error('Could not fetch server_url / release_version. Generation aborted.')
        wait_for_enter()
        return
    clear_screen()
    display_banner()
    summary = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    summary.add_column(style='dim', width=14)
    summary.add_column(style='bright_white')
    summary.add_row('Mode', f'[bold magenta]{mode_label}[/]' if is_ghost else f'[cyan]{mode_label}[/]')
    summary.add_row('Target', f'[green]{account_count}[/]')
    summary.add_row('Name', account_name)
    summary.add_row('Password', password_prefix)
    summary.add_row('Rarity', f'[cyan]{settings.RARITY_SCORE_THRESHOLD}+[/]')
    summary.add_row('Threads', f'[yellow]{thread_count}[/]')
    if use_proxy:
        summary.add_row('Connection', '[bold yellow]Proxy[/]')
    else:
        summary.add_row('Connection', '[green]Direct[/]')
    summary.add_row(
        'Activate',
        '[bold green]ON[/]' if activate_on_run else '[dim]OFF[/]',
    )
    summary.add_row('Output', settings.GHOST_ACCOUNTS_FOLDER if is_ghost else settings.ACCOUNTS_FOLDER)
    console.print(Panel(summary, title='[bold bright_cyan]ð  Run Summary[/]', border_style='bright_cyan', box=box.ROUNDED))
    time.sleep(0.03)
    settings.SUCCESS_COUNTER = 0
    settings.TARGET_ACCOUNTS = account_count
    settings.RARE_COUNTER = 0
    settings.COUPLES_COUNTER = 0
    settings.EXIT_FLAG = False
    settings.INFLIGHT_COUNTER = 0
    start_time = time.time()
    start_save_writer()
    start_live(account_count, selected_region, is_ghost, summary=summary_info)

    
    tasks = [
        asyncio.create_task(
            worker(selected_region, account_name, password_prefix, account_count, i + 1, is_ghost),
            name=f'worker-{i + 1}',
        )
        for i in range(thread_count)
    ]

    try:
        while any(not t.done() for t in tasks):
            if is_proxy_prompt_pending():
                stop_live()
                console.print()
                console.print('[bold yellow]â ï¸  Direct connection got 400/429 and proxies are available.[/]')
                try:
                    ans = Prompt.ask('[bold bright_cyan]Switch to proxy mode now? (y/n)[/]', default='y').strip().lower()
                except KeyboardInterrupt:
                    ans = 'n'
                enable = ans in ('y', 'yes')
                resolve_proxy_prompt(enable)
                if enable:
                    summary_info['connection'] = 'Proxy'
                    summary_info['use_proxy'] = True
                    use_proxy = True
                start_live(account_count, selected_region, is_ghost, summary=summary_info)
            with settings.LOCK:
                current = settings.SUCCESS_COUNTER
            elapsed = time.time() - start_time
            speed = current / elapsed if elapsed > 0 else 0.0
            update_live(current=current, rare=settings.RARE_COUNTER, couples=settings.COUPLES_COUNTER, elapsed=elapsed, speed=speed)
            if current >= account_count:
                settings.EXIT_FLAG = True
                break
            await asyncio.sleep(0.25)
    except KeyboardInterrupt:
        print_warning('Generation interrupted by user â saving buffered accountsâ¦')
        settings.EXIT_FLAG = True
        try:
            _proxy_hold.set()
        except Exception:
            pass
        try:
            stop_live()
        except Exception:
            pass
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            flush_saves()
            console.print('[dim]Buffered accounts saved.[/]')
        except Exception as e:
            print_warning(f'Save on interrupt failed: {e}')
        return

    settings.EXIT_FLAG = True
    try:
        _proxy_hold.set()
    except Exception:
        pass


    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5.0)
    except asyncio.TimeoutError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time
    with settings.LOCK:
        final_count = settings.SUCCESS_COUNTER
        final_rare = settings.RARE_COUNTER
        final_couples = settings.COUPLES_COUNTER
    speed = final_count / elapsed if elapsed > 0 else 0.0
    update_live(current=final_count, rare=final_rare, couples=final_couples, elapsed=elapsed, speed=speed, last_event='[green]â Generation finished[/]')
    stop_live()
    try:
        console.print('[dim]Writing accounts to disk (bulk)â¦[/]')
        flush_saves()
        console.print('[dim]Save complete.[/]')
    except Exception as e:
        print_warning(f'Save flush error: {e}')
    elapsed = time.time() - start_time
    speed = settings.SUCCESS_COUNTER / elapsed if elapsed > 0 else 0
    result = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    result.add_column(style='dim', width=14)
    result.add_column(style='bright_white')
    result.add_row('Generated', f'[green]{settings.SUCCESS_COUNTER}/{account_count}[/]')
    result.add_row('Rare', f'[cyan]{settings.RARE_COUNTER}[/]')
    result.add_row('Couples', f'[#FF69B4]{settings.COUPLES_COUNTER}[/]')
    result.add_row('Time', f'{elapsed:.2f}s')
    result.add_row('Speed', f'[yellow]{speed:.2f} acc/s[/]')
    if is_ghost:
        result.add_row('GHOST', settings.GHOST_ACCOUNTS_FOLDER)
        result.add_row('Rare GHOST', settings.GHOST_RARE_FOLDER)
        result.add_row('Couples GHOST', settings.GHOST_COUPLES_FOLDER)
    else:
        result.add_row('Accounts', settings.ACCOUNTS_FOLDER)
        result.add_row('Rare', settings.RARE_ACCOUNTS_FOLDER)
        result.add_row('Couples', settings.COUPLES_ACCOUNTS_FOLDER)
        result.add_row('JWT', settings.TOKENS_FOLDER)
    console.print()
    console.print(Panel(result, title='[bold green]â  Generation complete[/]', border_style='green', box=box.ROUNDED))
    wait_for_enter()

def view_saved_accounts() -> None:
    clear_screen()
    display_banner()
    account_files: list[str] = []
    if os.path.exists(settings.ACCOUNTS_FOLDER):
        account_files.extend((os.path.join(settings.ACCOUNTS_FOLDER, f) for f in os.listdir(settings.ACCOUNTS_FOLDER) if f.endswith('.json')))
    ghost_file = os.path.join(settings.GHOST_ACCOUNTS_FOLDER, 'ghost.json')
    if os.path.exists(ghost_file):
        account_files.append(ghost_file)
    if not account_files:
        console.print(Panel('[yellow]ð­ No saved accounts found.[/]', border_style='yellow', box=box.ROUNDED))
        wait_for_enter()
        return
    table = Table(box=box.ROUNDED, border_style='bright_blue', expand=True)
    table.add_column('File', style='cyan')
    table.add_column('Count', style='green', justify='right')
    total = 0
    for filepath in account_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
            count = len(accounts)
            table.add_row(os.path.basename(filepath), str(count))
            total += count
        except Exception as e:
            print_error(f'Error reading {filepath}: {e}')
    table.add_row('[bold]Total[/]', f'[bold]{total}[/]')
    console.print(Panel(table, title='[bold]ð Saved Accounts[/]', border_style='bright_blue', box=box.ROUNDED))
    wait_for_enter()

def about_section() -> None:
    clear_screen()
    display_banner()
    features = ['Multi-region Free Fire guest account generation', 'GHOST Mode for non region-locked accounts', 'Automatic JWT token extraction and storage', 'Multi-threaded generation with configurable thread count', 'Rare account detection with configurable rarity scoring', 'Couples account matching across threads', 'Thread-safe atomic JSON storage']
    feat_text = '\n'.join((f'  â¢ {f}' for f in features))
    locations = [('Accounts', settings.ACCOUNTS_FOLDER), ('JWT Tokens', settings.TOKENS_FOLDER), ('Rare Accounts', settings.RARE_ACCOUNTS_FOLDER), ('Couples', settings.COUPLES_ACCOUNTS_FOLDER), ('GHOST Accounts', settings.GHOST_ACCOUNTS_FOLDER)]
    loc_table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    loc_table.add_column(style='dim', width=16)
    loc_table.add_column(style='cyan')
    for label, path in locations:
        loc_table.add_row(label, path)
    console.print(Panel(feat_text, title='[bold bright_cyan]â¨  Features[/]', border_style='bright_cyan', box=box.ROUNDED))
    console.print(Panel(loc_table, title='[bold bright_cyan]ð  Storage[/]', border_style='bright_cyan', box=box.ROUNDED))
    wait_for_enter()

async def main_menu() -> None:
    while True:
        clear_screen()
        display_banner()
        menu = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
        menu.add_column(style='bold bright_white', width=4, justify='right')
        menu.add_column(style='bright_white')
        menu.add_row('1)', 'Generator')
        menu.add_row('2)', 'Activator')
        menu.add_row('3)', 'View Saved Accounts')
        menu.add_row('4)', '[red]Exit[/]')
        console.print(Panel(menu, title='[bold bright_cyan]â  SNOWFLAKE[/]  [dim]Â· Main Menu[/]', border_style='bright_cyan', box=box.ROUNDED))
        try:
            choice = Prompt.ask('[bold bright_cyan]ð¯ Choose option[/]', default='1').strip()
            if choice == '1':
                await generate_accounts_flow()
            elif choice == '2':
                activator_flow()
            elif choice == '3':
                view_saved_accounts()
            elif choice == '4':
                console.print('\n[bold green]ð Goodbye![/]')
                sys.exit(0)
            else:
                console.print('[bold red]Invalid option. Choose 1, 2, 3, or 4.[/]')
                time.sleep(1)
        except KeyboardInterrupt:
            safe_exit()

def _prompt_int(label: str, min_val: int=1, default: int | None=None) -> int:
    while True:
        try:
            raw = Prompt.ask(f'[bold bright_cyan]{label}[/]', default=str(default) if default is not None else None).strip()
            if not raw and default is not None:
                return default
            val = int(raw)
            if val >= min_val:
                return val
            console.print(f'[bold red]Please enter a number >= {min_val}.[/]')
        except ValueError:
            console.print('[bold red]Invalid input. Please enter a number.[/]')
        except KeyboardInterrupt:
            safe_exit()

def _prompt_str(label: str, default: str | None=None) -> str:
    while True:
        try:
            val = Prompt.ask(f'[bold bright_cyan]{label}[/]', default=default if default is not None else None).strip()
            if not val and default is not None:
                return default
            if val:
                return val
            console.print('[bold red]This field cannot be empty.[/]')
        except KeyboardInterrupt:
            safe_exit()

def install_requirements():
    print("Checking required packages...")
    all_ok = True
    for module, package in _REQUIRED.items():
        try:
            importlib.import_module(module)
            print(f"  OK {package}")
        except ImportError:
            print(f"  Installing {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"  OK {package} installed")
            except subprocess.CalledProcessError:
                print(f"  Failed to install {package}")
                all_ok = False
    return all_ok

if __name__ == "__main__":
    if os.environ.get('SNOWFLAKE_DEBUG', '').strip() in ('1', 'true', 'True', 'yes'):
        settings.DEBUG = True
    if not install_requirements():
        sys.exit(1)

    import urllib3
    from urllib3.exceptions import InsecureRequestWarning

    urllib3.disable_warnings(InsecureRequestWarning)
    signal.signal(signal.SIGINT, safe_exit)
    signal.signal(signal.SIGTERM, safe_exit)

    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        safe_exit()
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        time.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
