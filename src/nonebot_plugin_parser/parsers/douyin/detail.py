"""Douyin detail API helpers."""

from __future__ import annotations

import re
import time
import random
import string
from typing import Any, ClassVar
from urllib.parse import quote, urlencode
from collections.abc import Mapping

from gmssl import sm3, func
from httpx import AsyncClient

from ...constants import COMMON_TIMEOUT
from ...exception import ParseException

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ABogus:
    _filter = re.compile(r"%([0-9A-F]{2})")
    _ua_key = "\x00\x01\x0e"
    _end_string = "cus"
    _browser = "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|Win32"
    _reg: ClassVar[list[int]] = [
        1937774191,
        1226093241,
        388252375,
        3666478592,
        2842636476,
        372324522,
        3817729613,
        2969243214,
    ]
    _alphabet: ClassVar[dict[str, str]] = {
        "s0": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
        "s1": "Dkdpgh4ZKsQB80/Mfvw36XI1R25+WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
        "s2": "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
        "s3": "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe",
        "s4": "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe",
    }

    def __init__(self, user_agent: str = USER_AGENT):
        self.chunk: list[int] = []
        self.size = 0
        self.reg = self._reg[:]
        self.ua_code = self.generate_ua_code(user_agent)
        self.browser = self._browser
        self.browser_len = len(self.browser)
        self.browser_code = self.char_code_at(self.browser)

    @classmethod
    def list_1(cls, random_num: float | None = None, a: int = 170, b: int = 85, c: int = 45) -> list[int]:
        return cls.random_list(random_num, a, b, 1, 2, 5, c & a)

    @classmethod
    def list_2(cls, random_num: float | None = None, a: int = 170, b: int = 85) -> list[int]:
        return cls.random_list(random_num, a, b, 1, 0, 0, 0)

    @classmethod
    def list_3(cls, random_num: float | None = None, a: int = 170, b: int = 85) -> list[int]:
        return cls.random_list(random_num, a, b, 1, 0, 5, 0)

    @staticmethod
    def random_list(
        a: float | None = None,
        b: int = 170,
        c: int = 85,
        d: int = 0,
        e: int = 0,
        f: int = 0,
        g: int = 0,
    ) -> list[int]:
        r = a or random.random() * 10000
        values = [r, int(r) & 255, int(r) >> 8]
        values.extend((values[1] & b | d, values[1] & c | e, values[2] & b | f, values[2] & c | g))
        return values[-4:]

    @staticmethod
    def from_char_code(*args: int) -> str:
        return "".join(chr(code) for code in args)

    @classmethod
    def generate_string_1(
        cls,
        random_num_1: float | None = None,
        random_num_2: float | None = None,
        random_num_3: float | None = None,
    ) -> str:
        return (
            cls.from_char_code(*cls.list_1(random_num_1))
            + cls.from_char_code(*cls.list_2(random_num_2))
            + cls.from_char_code(*cls.list_3(random_num_3))
        )

    def generate_string_2(self, url_params: str, method: str = "GET") -> str:
        values = self.generate_string_2_list(url_params, method)
        end_check = 0
        for value in values:
            end_check ^= value
        values.extend(self.browser_code)
        values.append(end_check)
        return self.rc4_encrypt(self.from_char_code(*values), "y")

    def generate_ua_code(self, user_agent: str) -> list[int]:
        value = self.rc4_encrypt(user_agent, self._ua_key)
        return self.sum(self.generate_result(value, "s3"))

    def generate_string_2_list(self, url_params: str, method: str = "GET") -> list[int]:
        start_time = int(time.time() * 1000)
        end_time = start_time + random.randint(4, 8)
        params = self.generate_params_code(url_params)
        method_code = self.generate_method_code(method)
        return self.list_4(
            end_time >> 24 & 255,
            params[21],
            self.ua_code[23],
            end_time >> 16 & 255,
            params[22],
            self.ua_code[24],
            end_time >> 8 & 255,
            end_time & 255,
            start_time >> 24 & 255,
            start_time >> 16 & 255,
            start_time >> 8 & 255,
            start_time & 255,
            method_code[21],
            method_code[22],
            int(end_time / 256 / 256 / 256 / 256),
            int(start_time / 256 / 256 / 256 / 256),
            self.browser_len,
        )

    def compress(self, block: list[int]) -> None:
        words = self.generate_f(block)
        state = self.reg[:]
        for index in range(64):
            value = self.de(state[0], 12) + state[4] + self.de(self.pe(index), index)
            value = self.de(value & 0xFFFFFFFF, 7)
            mix = (value ^ self.de(state[0], 12)) & 0xFFFFFFFF
            left = (self.he(index, state[0], state[1], state[2]) + state[3] + mix + words[index + 68]) & 0xFFFFFFFF
            right = (self.ve(index, state[4], state[5], state[6]) + state[7] + value + words[index]) & 0xFFFFFFFF
            state[3], state[2], state[1], state[0] = state[2], self.de(state[1], 9), state[0], left
            state[7], state[6], state[5], state[4] = (
                state[6],
                self.de(state[5], 19),
                state[4],
                (right ^ self.de(right, 9) ^ self.de(right, 17)) & 0xFFFFFFFF,
            )
        self.reg = [(old ^ new) & 0xFFFFFFFF for old, new in zip(self.reg, state)]

    @classmethod
    def generate_f(cls, values: list[int]) -> list[int]:
        result = [0] * 132
        for index in range(16):
            offset = index * 4
            result[index] = (
                values[offset] << 24 | values[offset + 1] << 16 | values[offset + 2] << 8 | values[offset + 3]
            ) & 0xFFFFFFFF
        for index in range(16, 68):
            value = result[index - 16] ^ result[index - 9] ^ cls.de(result[index - 3], 15)
            value ^= cls.de(value, 15) ^ cls.de(value, 23)
            result[index] = (value ^ cls.de(result[index - 13], 7) ^ result[index - 6]) & 0xFFFFFFFF
        for index in range(68, 132):
            result[index] = (result[index - 68] ^ result[index - 64]) & 0xFFFFFFFF
        return result

    def fill(self, length: int = 60) -> None:
        self.chunk.append(128)
        self.chunk.extend([0] * (length - len(self.chunk)))
        bit_length = 8 * self.size
        self.chunk.extend((bit_length >> shift) & 255 for shift in (24, 16, 8, 0))

    @staticmethod
    def list_4(
        a: int,
        b: int,
        c: int,
        d: int,
        e: int,
        f: int,
        g: int,
        h: int,
        i: int,
        j: int,
        k: int,
        m: int,
        n: int,
        o: int,
        p: int,
        q: int,
        r: int,
    ) -> list[int]:
        return [
            44,
            a,
            0,
            0,
            0,
            0,
            24,
            b,
            n,
            0,
            c,
            d,
            0,
            0,
            0,
            1,
            0,
            239,
            e,
            o,
            f,
            g,
            0,
            0,
            0,
            0,
            h,
            0,
            0,
            14,
            i,
            j,
            0,
            k,
            m,
            3,
            p,
            1,
            q,
            1,
            r,
            0,
            0,
            0,
        ]

    @staticmethod
    def de(value: int, shift: int) -> int:
        shift %= 32
        return ((value << shift) & 0xFFFFFFFF) | (value >> (32 - shift))

    @staticmethod
    def pe(index: int) -> int:
        return 2043430169 if index < 16 else 2055708042

    @staticmethod
    def he(index: int, x: int, y: int, z: int) -> int:
        return (x ^ y ^ z) & 0xFFFFFFFF if index < 16 else (x & y | x & z | y & z) & 0xFFFFFFFF

    @staticmethod
    def ve(index: int, x: int, y: int, z: int) -> int:
        return (x ^ y ^ z) & 0xFFFFFFFF if index < 16 else (x & y | ~x & z) & 0xFFFFFFFF

    @staticmethod
    def char_code_at(value: str) -> list[int]:
        return [ord(char) for char in value]

    def write(self, value: str | list[int]) -> None:
        self.size = len(value)
        values = self.char_code_at(self.decode_string(value)) if isinstance(value, str) else value
        if len(values) <= 64:
            self.chunk = values[:]
        else:
            chunks = [values[index : index + 64] for index in range(0, len(values), 64)]
            for chunk in chunks[:-1]:
                self.compress(chunk)
            self.chunk = chunks[-1]

    def reset(self) -> None:
        self.chunk = []
        self.size = 0
        self.reg = self._reg[:]

    def sum(self, value: str | list[int]) -> list[int]:
        self.reset()
        self.write(value)
        self.fill()
        self.compress(self.chunk)
        result = [0] * 32
        for index, value in enumerate(self.reg):
            result[index * 4] = value >> 24 & 255
            result[index * 4 + 1] = value >> 16 & 255
            result[index * 4 + 2] = value >> 8 & 255
            result[index * 4 + 3] = value & 255
        return result

    @classmethod
    def decode_string(cls, value: str) -> str:
        return cls._filter.sub(lambda match: chr(int(match.group(1), 16)), value)

    @classmethod
    def generate_result(cls, value: str, alphabet: str = "s4") -> str:
        result: list[str] = []
        for index in range(0, len(value), 3):
            chunk = value[index : index + 3]
            number = sum(ord(char) << (16 - offset * 8) for offset, char in enumerate(chunk))
            for shift, mask in ((18, 0xFC0000), (12, 0x03F000), (6, 0x0FC0), (0, 0x3F)):
                if (shift == 6 and len(chunk) < 2) or (shift == 0 and len(chunk) < 3):
                    continue
                result.append(cls._alphabet[alphabet][(number & mask) >> shift])
        return "".join(result) + "=" * ((4 - len(result) % 4) % 4)

    def generate_method_code(self, method: str = "GET") -> list[int]:
        return self.sm3_to_array(self.sm3_to_array(method + self._end_string))

    def generate_params_code(self, params: str) -> list[int]:
        return self.sm3_to_array(self.sm3_to_array(params + self._end_string))

    @staticmethod
    def sm3_to_array(value: str | list[int]) -> list[int]:
        raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        digest = sm3.sm3_hash(func.bytes_to_list(raw))
        return [int(digest[index : index + 2], 16) for index in range(0, len(digest), 2)]

    @staticmethod
    def rc4_encrypt(value: str, key: str) -> str:
        state = list(range(256))
        cursor = 0
        for index in range(256):
            cursor = (cursor + state[index] + ord(key[index % len(key)])) % 256
            state[index], state[cursor] = state[cursor], state[index]
        output: list[str] = []
        index = cursor = 0
        for char in value:
            index = (index + 1) % 256
            cursor = (cursor + state[index]) % 256
            state[index], state[cursor] = state[cursor], state[index]
            output.append(chr(ord(char) ^ state[(state[index] + state[cursor]) % 256]))
        return "".join(output)

    def get_value(self, params: Mapping[str, Any], method: str = "GET") -> str:
        query = urlencode(params, quote_via=quote)
        return self.generate_result(self.generate_string_1() + self.generate_string_2(query, method), "s4")


def _random_token() -> str:
    return "".join(random.choice(string.digits + string.ascii_letters) for _ in range(156))


async def fetch_aweme_detail(aweme_id: str) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.douyin.com/"}
    ms_token = _random_token()
    async with AsyncClient(headers=headers, verify=False, timeout=COMMON_TIMEOUT, follow_redirects=True) as client:
        cookies: dict[str, str] = {"msToken": ms_token}
        try:
            response = await client.post(
                "https://ttwid.bytedance.com/ttwid/union/register/",
                json={
                    "region": "cn",
                    "aid": 1768,
                    "needFid": False,
                    "service": "www.ixigua.com",
                    "migrate_info": {"ticket": "", "source": "node"},
                    "cbUrlProtocol": "https",
                    "union": True,
                },
            )
            response.raise_for_status()
            cookies.update(dict(response.cookies))
        except Exception:
            pass

        params: dict[str, str] = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "aweme_id": aweme_id,
            "update_version_code": "170400",
            "pc_client_type": "1",
            "version_code": "190500",
            "version_name": "19.5.0",
            "cookie_enabled": "true",
            "platform": "PC",
            "downlink": "10",
            "msToken": ms_token,
        }
        params["a_bogus"] = ABogus(USER_AGENT).get_value(params)
        response = await client.get(
            "https://www.douyin.com/aweme/v1/web/aweme/detail/",
            params=params,
            headers={**headers, "Accept": "application/json, text/plain, */*"},
            cookies=cookies,
        )
        response.raise_for_status()
        if not response.content:
            raise ParseException("抖音详情接口返回空响应")
        data = response.json()
        detail = data.get("aweme_detail")
        if not isinstance(detail, dict):
            raise ParseException("抖音详情接口未返回 aweme_detail")
        return detail
