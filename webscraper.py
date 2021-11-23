import bs4
import requests

#import line_profiler_pycharm



headers = {
    "User-Agent": 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
}


def RemoveDuplicatedPreserveOrder(listData) -> list:
    seen = set()
    
    return [data for data in listData if not (data in seen or seen.add(data))]


def GetLatestDataAnimeDaoTo() -> list:
    def parseTitleEp(titleEpString, default=None) -> tuple:
        nameSplit = titleEpString.split(" ")
        reversedNameSplit = nameSplit[::-1]

        episodeNumber = reversedNameSplit.pop(0)

        try:
            return True, int(episodeNumber), " ".join(reversedNameSplit[1:][::-1])  # Some can be float but ignore them
        except ValueError:
            return False, default, ""

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


if __name__ == "__main__":
    from time import time

    s = time()
    data = GetLatestDataAnimeDaoTo()
    e = time() - s

    print(f"{round(e*1000)}ms")
    #pprint(data)
