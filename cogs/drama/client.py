# pyright: reportOptionalMemberAccess=false, reportUnknownVariableType=false
import json
import re
from typing import Any

import bs4
import curl_cffi
from _types import MDLMedia, MDLSearchMedia, MDLSearchPeople


class MyDramaList:
    BASE_URL = "https://mydramalist.com"

    def __init__(self):
        self._session: Any = curl_cffi.AsyncSession(impersonate="chrome120")


    async def close(self):
        await self._session.close()


    def format(self, string: str) -> str:
        return string.replace("  ", " ").removeprefix(" ").removesuffix(" ").replace(" ,", ",")


    async def search_media(self, terms: str, page: int = 1) -> list[MDLSearchMedia]:
        "Search for any type of media on MyDramaList. Returns a list of results."
        req = await self._session.get(
            f"{self.BASE_URL}/search", params={"q": terms, "page": page, "adv": "titles", "so": "relevance"}
        )

        if req.status_code != 200:
            raise Exception(f"Failed to fetch, received a {req.status_code} status code.")

        soup = bs4.BeautifulSoup(req.text, "html.parser")

        cards = soup.find("div", class_="b-primary")
        if not cards:
            return []

        results = cards.find_all("div", class_="box")

        res: list[MDLSearchMedia] = []
        for result in results:
            title = result.find("h6", class_="title").text.strip()
            score = result.find("span", class_="score").text
            image_uri = result.find("img").attrs["data-src"]

            ranking = ""
            if item := result.find("div", class_="ranking"):
                ranking = item.text[1:]

            slug = result.find("a")["href"]  # pyright: ignore[reportOptionalSubscript]
            _id, *_ = slug[1:].split("-", 1)  # type: ignore

            uri = f"{self.BASE_URL}{slug}"

            type_, yearNEpisodes = result.find("span", class_="text-muted").text.split(" - ")

            year, *episodes = yearNEpisodes.split(", ")
            if not episodes:
                episodes = "0"
            short_desc = result.select_one("p:last-of-type").text

            res.append(
                {
                    "id": _id,
                    "title": title,
                    "uri": uri,
                    "image_uri": str(image_uri),
                    "score": score,
                    "ranking": ranking,
                    "type": type_,
                    "year": year,
                    "amt_episodes": int(episodes[0].split()[0]),
                    "short_desc": short_desc,
                }
            )

        return res


    async def search_people(self, terms: str, page: int = 1) -> list[MDLSearchPeople]:
        "Search for actors/actresses on MyDramaList. Returns a list of results."
        req = await self._session.get(
            f"{self.BASE_URL}/search", params={"q": terms, "page": page, "adv": "people", "so": "relevance"}
        )

        if req.status_code != 200:
            raise Exception(f"Failed to fetch, received a {req.status_code} status code.")

        soup = bs4.BeautifulSoup(req.text, "html.parser")

        cards = soup.find("div", class_="b-primary")
        if not cards:
            return []

        results = cards.find_all("div", class_="box")

        res: list[MDLSearchPeople] = []
        for result in results:
            title = result.find("h6", class_="title").text.strip()

            slug = result.find("a")["href"]  # pyright: ignore[reportOptionalSubscript]
            _id, *_ = slug[1:].split("-", 1)  # type: ignore

            uri = f"{self.BASE_URL}{slug}"

            nationality = result.find("span", class_="spacer").text
            short_desc = result.select_one("p:last-of-type").text

            res.append(
                {
                    "id": _id,
                    "title": title,
                    "uri": uri,
                    "nationality": nationality,
                    "short_desc": short_desc,
                }
            )

        return res


    async def fetch_media(self, terms: str) -> MDLMedia:
        media = (await self.search_media(terms))[0]
        req = await self._session.get(media["uri"])
        if req.status_code != 200:
            raise Exception(f"Failed to fetch, received a {req.status_code} status code.")

        soup = bs4.BeautifulSoup(req.text, "html.parser")
        res: dict[str, Any] = {}

        res["title"] = soup.find("h1", class_="film-title").text
        res["native_title"] = soup.find("div", class_="film-subtitle").text.split(" ‧ ")[0]
        res["description"] = re.sub(
            "\\s*\\(Source:.*", "", soup.find("div", class_="show-synopsis").find("p").find("span").text
        )

        attrs = soup.find("div", class_="show-detailsxss").find_all("li")
        for tag in attrs:
            if tag.text.startswith(" Related Content"):
                continue
            k, v = tag.text.split(": ", maxsplit=1)
            res[self.format(k)] = self.format(v)

        extra_attrs = json.loads(soup.find("script", type="application/ld+json").text)
        res["url"] = extra_attrs["url"]
        res["image_uri"] = extra_attrs["image"]
        res["genres"] = extra_attrs["genre"]
        res["tags"] = extra_attrs["keywords"]
        res["country"] = extra_attrs["countryOfOrigin"]["name"]
        res["rating"] = extra_attrs["aggregateRating"]["ratingValue"]
        res["rating_users"] = extra_attrs["aggregateRating"]["ratingCount"]
        if res.get("Aired On"):
            res["daysofweek"] = res.get("Aired On").split(", ")

        for key in [
            "Native Title",
            "Also Known As",
            "Genres",
            "Tags",
            "Watchers",
            "Favorites",
            "Aired On",
            "Score",
            "Popularity",
        ]:
            try:
                del res[key]
            except KeyError:
                continue

        for key in res.copy():
            val = res[key]
            del res[key]
            res[key.lower().replace("&", "").replace("  ", "_").replace(" ", "_")] = val

        if res.get("screenwriter"):
            res["screenwriter"] = res["screenwriter"].split(", ")
        if res.get("director"):
            res["director"] = res["director"].split(", ")
        res.setdefault("director", [])
        res.setdefault("screenwriter", [])
        if res.get("screenwriter_director"):
            res["screenwriter"].extend(res["screenwriter_director"].split(", "))
            res["director"].extend(res["screenwriter_director"].split(", "))
            del res["screenwriter_director"]

        return res  # pyright: ignore[reportReturnType]