import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urlparse

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

    number = None
    try:
        number = float(episodeNumber)
        number = int(episodeNumber)

        return True, number, " ".join(reversedNameSplit[1:][::-1])
    except ValueError:
        if isinstance(number, float):
            return True, number, " ".join(reversedNameSplit[1:][::-1])

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


def GetAniGenres(aniData):
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


def GetAniData(aniUrl):
    urlRequest = requests.get(aniUrl, headers=headers)
    baseUrl = r"https://animedao.to"

    if urlRequest.status_code == 200:
        content = urlRequest.content
        # print(getsizeof(content))

        tree = bs4.BeautifulSoup(content, 'lxml')
        episodeHref = [a for a in tree.find_all("a") if "view" in a["href"]]
        episodeData = [[a["href"], a.find("div", {"class": "anime-title"})] for a in episodeHref]

        episodeData = [{"view": baseUrl + data[0], "title": data[1].text.strip(), "name": data[1].parent.find_all("span")[-1]["title"]} for data in episodeData if data[1].parent.find_all("span")[-1].get("title", "")]

        description = tree.find("div", {"id": "demo"}).text.strip()
        icon = baseUrl + tree.find("img")["src"]

        title = "-".join(tree.title.text.split("-")[:-1]).strip()

        return title, icon, description, episodeData

    return None, None, None, None


def extractVideoFiles(aniEpUrl, repeat=5, currentRepeat=0):
    def getUrlProtocolDomain(url):
        urlParsed = urlparse(url)
        return urlParsed.scheme, urlParsed.netloc, urlParsed.path.split("/")[1]

    def recursiveGetVideoUrl(url, finished=False, finalIndexOverride=None):
        newUrl = url
        logging.info(f"Webscraper: Requesting {url}")

        if not finished:
            urlRequest = requests.get(url, headers=headers)

            endUrl = urlRequest.url
            urlContent = urlRequest.content

            if urlRequest.status_code == 200:
                tree = bs4.BeautifulSoup(urlContent, 'lxml')

                urlScheme, urlDomain, urlBasePath = getUrlProtocolDomain(endUrl)
                logging.info(f"Webscraper: Received {endUrl} : {urlScheme} {urlDomain} {urlBasePath}")

                if urlDomain == "vstream1.xyz":
                    newUrl = urlScheme + ":" + tree.iframe["src"]

                elif urlDomain == "gogoplay1.com":
                    if urlBasePath == "streaming.php":
                        #links = tree.find_all("li", {"class": "linkserver"})
                        #links = [link["data-video"] for link in links if link["data-video"]]
                        #newUrl = links[0]

                        pageId = endUrl.replace(r"https://gogoplay1.com/streaming.php?id=", "")
                        newUrl = f"https://gogoplay1.com/download?id={pageId}&title=&typesub="

                    elif urlBasePath == "embedplus":
                        link = re.search("https://gogoplay(.*?)typesub=", urlContent.decode("utf-8"))

                        if not link:
                            iframes = tree.find_all("iframe", {"id": "embedvideo"})

                            if len(iframes) > 0:
                                newUrl = iframes[0]["src"]
                        else:
                            newUrl = link.group()

                    elif urlBasePath == "download":
                        aLinks = tree.find_all("a", {"target": "_blank"})
                        links = [aLink["href"] for aLink in aLinks]

                        newUrl = links[0]

                elif urlDomain == "sbplay2.com":
                    if urlBasePath == "d":
                        aTags = tree.find_all("a", {"href": "#"})
                        functionCalls = [aTag.get("onclick") for aTag in aTags if aTag.get("onclick")]
                        functionMatches = [re.search("download_video\('(.*?)','(.*?)','(.*?)'\)", call) for call in functionCalls]
                        functionParams = [(match.group(1), match.group(2), match.group(3)) for match in functionMatches]

                        downloadInfo = [aTag.parent.parent.find_all("td")[1].text for aTag in aTags if aTag.get("onclick")]

                        #functionParam = functionParams[finalIndexOverride or -1]

                        #print(functionParams)

                        finished = True
                        newUrl = [recursiveGetVideoUrl(f"{urlScheme}://{urlDomain}/dl?op=download_orig&id={functionParam[0]}&mode={functionParam[1]}&hash={functionParam[2]}") for functionParam in functionParams]
                        newUrl = list(zip(newUrl, downloadInfo))

                    elif urlBasePath == "dl":
                        if not tree.find("b", {"class": "err"}):
                            aTags = tree.find_all("a")
                            aTexts = [aTag.text for aTag in aTags]
                            #print(aTexts)
                            downloadA = [aTag["href"] for aTag in aTags if aTag.text == "Direct Download Link"][0]

                            newUrl = downloadA
                            finished = True

                            #print("FINISHED", newUrl)

                elif urlDomain == "playdrive.xyz" or urlDomain == "mixdrop.to":
                    if urlBasePath == "e":
                        newUrl = "empty"
                        finished = True

                elif urlDomain == "streamsb.net":
                    newUrl = "empty"
                    finished = True

                elif urlDomain == "vcdn2.space":
                    if urlBasePath == "v":
                        newUrl = "empty"
                        finished = True

                elif urlDomain == "www.mp4upload.com":
                    newUrl = "empty"
                    finished = True

                else:
                    newUrl = "empty"
                    finished = True

                logging.info(f"Webscraper: New {newUrl}")

            else:
                newUrl = "empty"
                finished = True

        if finished:
            logging.info("Webscraper: --------------------------------------------")
            pass

        return finished and newUrl or recursiveGetVideoUrl(newUrl)

    #aniEpUrl = r"https://animedao.to/view/431131313/"
    urlRequest = requests.get(aniEpUrl, headers=headers)
    baseUrl = r"https://animedao.to"
    logging.info(f"Webscraper: Scanning {aniEpUrl}")

    if urlRequest.status_code == 200:
        logging.info(f"Webscraper: Scanning - In Progress")

        content = urlRequest.content
        # print(getsizeof(content))

        tree = bs4.BeautifulSoup(content, 'lxml')
        scripts = tree.find_all("script")
        scripts = [script.text for script in scripts if "/redirect/" in script.text or "playdrive.xyz" in script.text]

        iframes = [re.search("<iframe (.*?)</iframe>", script) for script in scripts]
        iframes = [iframeRe.group() for iframeRe in iframes if iframeRe]

        sources = [re.search(r'src\s*=\s*"(.+?)"', iframe).group(1) for iframe in iframes]
        sources = ["redirect" in source and baseUrl + source or source for source in sources]

        urls = []
        for url in sources:
            endUrl = recursiveGetVideoUrl(url)
            urls.append(endUrl)

            if endUrl != "empty":
                break

        urlsFinal = []
        for url in urls:
            if url != "empty":
                if isinstance(url, list):
                    urlsFinal.extend(url)
                else:
                    urlsFinal.append(url)

        logging.info(f"Webscraper: Final Urls {urlsFinal}")

        return urlsFinal

    else:
        logging.info(f"Webscraper: Scanning - Failed")

        if currentRepeat <= repeat:
            logging.info(f"Webscraper: Repeating at {currentRepeat+1}, Max {repeat}")

            return extractVideoFiles(aniEpUrl, repeat=repeat, currentRepeat=currentRepeat+1)

        logging.info(f"Webscraper: Scanning - Failed, View URL is broken")
        return []


if __name__ == "__main__":
    from time import time

    s = time()
    data2 = extractVideoFiles(r"https://animedao.to/view/4704419159/")
    print(data2)
    e = time() - s

    print(f"{round(e*1000)}ms")
    #pprint(data)

    #SearchDataAnimeDaoTo("Sword Art Online")
