import base64
import re
from typing import Optional

import aiohttp
from pyquery import PyQuery
from yarl import URL

from .config import config


# 将图片转化为 base64
async def get_pic_base64_by_url(url: str, cookies: Optional[str] = None) -> str:
    headers = {}
    if cookies:
        headers["Cookie"] = cookies
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, proxy=config.proxy) as resp:
            if resp.status == 200:
                return base64.b64encode(await resp.read()).decode()
    return f"预览图链接：{url}"


async def handle_img(
    url: str,
    hide_img: bool,
    cookies: Optional[str] = None,
) -> str:
    if not hide_img:
        if img_base64 := await get_pic_base64_by_url(url, cookies):
            return f"[CQ:image,file=base64://{img_base64}]"
    return f"预览图链接：{url}"


async def get_source(url: str) -> str:
    source = ""
    async with aiohttp.ClientSession() as session:
        if URL(url).host == "danbooru.donmai.us":
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
                    source = PyQuery(html)("#stats li:contains(Source) a").attr("href")
        elif URL(url).host == "gelbooru.com":
            async with session.get(url, proxy=config.proxy) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    source = PyQuery(html)("#tag-list li:contains(Source) a").attr(
                        "href"
                    )
    return str(source)


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
