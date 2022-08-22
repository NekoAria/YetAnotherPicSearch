import functools
import re
from base64 import b64encode
from contextlib import suppress
from typing import List, Optional

import aiohttp
from cachetools import TTLCache
from cachetools.keys import hashkey
from nonebot.adapters.onebot.v11 import Bot
from pyquery import PyQuery
from yarl import URL

from .config import config


# 将图片转化为 base64
async def get_pic_base64_by_url(url: str, cookies: Optional[str] = None) -> str:
    headers = {"Cookie": cookies} if cookies else None
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, proxy=config.proxy) as resp:
            if resp.status == 200 and (image_bytes := await resp.read()):
                return b64encode(image_bytes).decode()
    return ""


async def handle_img(
    url: str,
    hide_img: bool,
    cookies: Optional[str] = None,
) -> str:
    if not hide_img:
        if img_base64 := await get_pic_base64_by_url(url, cookies):
            return f"[CQ:image,file=base64://{img_base64}]"
    return f"预览图链接：{url}"


def cached_async(cache, key=hashkey):  # type: ignore
    """
    https://github.com/tkem/cachetools/commit/3f073633ed4f36f05b57838a3e5655e14d3e3524
    """

    def decorator(func):  # type: ignore
        if cache is None:

            async def wrapper(*args, **kwargs):  # type: ignore
                return await func(*args, **kwargs)

        else:

            async def wrapper(*args, **kwargs):  # type: ignore
                k = key(*args, **kwargs)
                with suppress(KeyError):  # key not found
                    return cache[k]
                v = await func(*args, **kwargs)
                with suppress(ValueError):  # value too large
                    cache[k] = v
                return v

        return functools.update_wrapper(wrapper, func)

    return decorator


@cached_async(TTLCache(maxsize=1, ttl=300))  # type: ignore
async def get_bot_friend_list(bot: Bot) -> List[int]:
    friend_list = await bot.get_friend_list()
    return [i["user_id"] for i in friend_list]


def handle_reply_msg(message_id: int) -> str:
    return f"[CQ:reply,id={message_id}]"


async def get_source(url: str) -> str:
    source = ""
    async with aiohttp.ClientSession() as session:
        if URL(url).host in ["danbooru.donmai.us", "gelbooru.com"]:
            async with session.get(url, proxy=config.proxy) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    source = PyQuery(html)(".image-container").attr(
                        "data-normalized-source"
                    )
        elif URL(url).host in ["yande.re", "konachan.com"]:
            async with session.get(url, proxy=config.proxy) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    source = PyQuery(html)("#post_source").attr("value")
    return source


async def shorten_url(url: str) -> str:
    pid_search = re.compile(
        r"(?:pixiv.+(?:illust_id=|artworks/)|/img-original/img/(?:\d+/){6})(\d+)"
    )
    if pid_search.search(url):
        return f"https://pixiv.net/i/{pid_search.search(url)[1]}"  # type: ignore
    if URL(url).host == "danbooru.donmai.us":
        return url.replace("/post/show/", "/posts/")
    if URL(url).host in ["exhentai.org", "e-hentai.org"]:
        flag = len(url) > 1024
        async with aiohttp.ClientSession() as session:
            if not flag:
                resp = await session.post("https://yww.uy/shorten", json={"url": url})
                if resp.status == 200:
                    return (await resp.json())["url"]  # type: ignore
                else:
                    flag = True
            if flag:
                resp = await session.post(
                    "https://www.shorturl.at/shortener.php", data={"u": url}
                )
                if resp.status == 200:
                    html = await resp.text()
                    final_url = PyQuery(html)("#shortenurl").attr("value")
                    return f"https://{final_url}"
    return url
