from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import bs4
import requests

#import line_profiler_pycharm


headers = {
    "User-Agent": 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
}


def RemoveDuplicatedPreserveOrder(listData) -> list:
    seen = set()
    
    return [data for data in listData if not (data in seen or seen.add(data))]


def parseTitleEp(titleEpString, default=None) -> tuple:
    nameSplit = titleEpString.split(" ")
    reversedNameSplit = nameSplit[::-1]

    episodeNumber = reversedNameSplit.pop(0)

    try:
        return True, int(episodeNumber), " ".join(reversedNameSplit[1:][::-1])  # Some can be float but ignore them
    except ValueError:
        return False, default, ""


def GetLatestDataAnimeDaoTo() -> list:
    url = r"https://animedao.to"

    urlRequest = requests.get(url, headers=headers)
    #urlRequest = None

    if True or urlRequest.status_code == 200:
        content = urlRequest.content
        #file = open("AnimeDao.html", mode="r", encoding="utf8")
        #content = file.read()
        #file.close()

        tree = bs4.BeautifulSoup(content, 'lxml')

        divLatestGroup = tree.findAll('div', {"class": "col-xs-12 col-sm-6 col-md-6 col-lg-4"})
        divLatestGroup = [div.findAll('div', {"class": "row"})[0] for div in divLatestGroup if div.parent["class"] == ['tab-pane', 'fade', 'active', 'in']]

        aniDataSplit = [[div.findAll('img')[0]["data-src"], div.findAll('a'), div.findAll("span", {"class": "latestanime-subtitle"})] for div in divLatestGroup]

        aniData = []
        for data in aniDataSplit:
            successful, episodeNumber, extraName = parseTitleEp(data[1][0]["title"])

            if successful:
                data = {"title": data[1][2]["title"],
                        "name": extraName,
                        "episode": episodeNumber,
                        "source": data[2][0].get("title", ""),
                        "thumbnail": url + data[0],
                        "view": url + data[1][0]["href"],
                        "ani": url + data[1][2]["href"]}

                aniData.append(data)

        return aniData

    return []


def SearchDataAnimeDaoTo(query):
    baseUrl = r"https://animedao.to"
    requestUrl = f"{baseUrl}/search/?search={quote_plus(query)}"

    urlRequest = requests.get(requestUrl, headers=headers)

    if urlRequest.status_code == 200:
        content = urlRequest.content
        #print(getsizeof(content))

        tree = bs4.BeautifulSoup(content, 'lxml')

        divLatestGroup = tree.findAll('div', {"class": "col-xs-12 col-sm-6 col-md-6 col-lg-4"})

        aniData = []

        for div in divLatestGroup:
            data = {}

            aniLink = div.findAll("a")[0].get("href", "")
            data["ani"] = baseUrl + aniLink

            imageLink = div.findAll('img')[0]["data-src"]
            data["thumbnail"] = baseUrl + imageLink

            nameData = div.findAll("div", {"class": "ongoingtitle"})[0]
            title = nameData.findAll("b")[0].text
            titleData = nameData.findAll("small")[0].text

            data["name"] = title
            data["nameExtra"] = titleData

            aniData.append(data)

        return aniData

    return []


def GetAnimeGenres(aniData):
    def getAniGenre(aniUrl):
        baseUrl = r"https://animedao.to"

        urlRequest = requests.get(aniUrl, headers=headers)

        if urlRequest.status_code == 200:
            content = urlRequest.content
            # print(getsizeof(content))

            tree = bs4.BeautifulSoup(content, 'lxml')
            genreHrefs = tree.find_all("a", {"class": "animeinfo_label"})

            return [a.get("href", "").split("=")[-1] for a in genreHrefs]

        return []

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(getAniGenre, [data["ani"] for data in aniData])

    return [genre for genre in results]


if __name__ == "__main__":
    from time import time

    s = time()
    data = SearchDataAnimeDaoTo("Sword Art online")
    data2 = GetAnimeGenres(data)
    print(data2)
    e = time() - s

    print(f"{round(e*1000)}ms")
    #pprint(data)

    #SearchDataAnimeDaoTo("Sword Art Online")
