import logging
import queue
import re
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from urllib.parse import quote_plus, urlparse

import bs4
import requests
import cchardet
import socket

#import line_profiler_pycharm
from user_agent import generate_navigator_js
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from kivy.utils import platform
if platform == "win":
    from subprocess import CREATE_NO_WINDOW

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from time import sleep, time
import threading

headers = {
    "User-Agent": 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'
}


def isConnected():
    try:
        # connect to the host -- tells us if the host is actually
        # reachable
        sock = socket.create_connection(("www.google.com", 80))
        if sock is not None:
            sock.close()
        return True
    except OSError:
        pass
    return False


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


def GetLatestDataAnimeDaoTo(mode="gogoanime") -> list:
    url = mode == "animedao" and r"https://animedao.to" or r"https://www1.gogoanime.cm"

    if isConnected():
        urlRequest = requests.get(url, headers=headers)
        logging.info(f"Webscraper: Getting Latest - {url} - {mode}")
        #urlRequest = None

        if urlRequest.status_code == 200:
            content = urlRequest.content
            #file = open("AnimeDao.html", mode="r", encoding="utf8")
            #content = file.read()
            #file.close()

            tree = bs4.BeautifulSoup(content, 'lxml')

            if mode == "animedao":
                divLatestGroup = tree.findAll('div', {"class": "col-xs-12 col-sm-6 col-md-6 col-lg-4"})
                divLatestGroup = [div.findAll('div', {"class": "row"})[0] for div in divLatestGroup if div.parent["class"] == ['tab-pane', 'fade', 'active', 'in']]

                aniDataSplit = [[div.findAll('img')[0]["data-src"], div.findAll('a'), div.findAll("span", {"class": "latestanime-subtitle"})] for div in divLatestGroup]

                aniData = []
                for data in aniDataSplit:
                    successful, episodeNumber, extraName = parseTitleEp(data[1][0]["title"])

                    if successful:
                        data = {#"title": data[1][2]["title"],
                                "name": extraName,
                                "episode": episodeNumber,
                                #"source": data[2][0].get("title", ""),
                                "thumbnail": url + data[0],
                                #"view": url + data[1][0]["href"],
                                "ani": url + data[1][2]["href"]
                               }

                        aniData.append(data)

                return aniData
            elif mode == "gogoanime":
                aniData = []

                items = tree.find("ul", {"class": "items"})
                for liTag in items.find_all("li"):
                    imageSrc = liTag.find("img")["src"]
                    name = liTag.find("a")["title"]
                    
                    try:
                        episode = int(liTag.find("p", {"class": "episode"}).text.split(" ")[-1])
                    except ValueError:
                        logging.info(f"Webscraper Latest: {name} Has Non-Integer Episode")
                        continue
                    
                    aniName = ".".join(imageSrc.split("/")[-1].split(".")[:-1])
                    aniSource = f"https://www1.gogoanime.cm/category/{aniName}"

                    data = {  # "title": data[1][2]["title"],
                        "name": name,
                        "episode": episode,
                        # "source": data[2][0].get("title", ""),
                        "thumbnail": imageSrc,
                        # "view": url + data[1][0]["href"],
                        "ani": aniSource
                    }

                    aniData.append(data)

                return aniData

            else:
                return GetLatestDataAnimeDaoTo(mode="animedao")
    else:
        logging.info(f"Webscraper: Latest Data - No Connection..")

    return []


def SearchDataAnimeDaoTo(query, mode="gogoanime"):
    if mode == "animedao":
        baseUrl = r"https://animedao.to"
        requestUrl = f"{baseUrl}/search/?search={quote_plus(query)}"
    elif mode == "gogoanime":
        baseUrl = r"https://www1.gogoanime.cm"
        requestUrl = f"{baseUrl}//search.html?keyword={quote_plus(query)}"
    else:
        return SearchDataAnimeDaoTo(query, mode="animedao")

    if isConnected():
        urlRequest = requests.get(requestUrl, headers=headers)
        logging.info(f"Webscraper: Searching Query - {requestUrl} - {mode}")

        if urlRequest.status_code == 200:
            content = urlRequest.content
            #print(getsizeof(content))

            tree = bs4.BeautifulSoup(content, 'lxml')

            if mode == "animedao":
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

            elif mode == "gogoanime":
                items = tree.find("ul", {"class": "items"})

                aniData = []

                for liTag in items.find_all("li"):
                    imageSrc = liTag.find("img")["src"]
                    name = liTag.find("a")["title"]
                    aniSource = baseUrl + liTag.find("a")["href"]

                    data = {
                        "name": name,
                        "thumbnail": imageSrc,
                        "ani": aniSource
                    }

                    aniData.append(data)

                return aniData

            else:
                return SearchDataAnimeDaoTo(query, mode="animedao")
    else:
        logging.info(f"Webscraper: Search - No Connection")

    return []


def GetAniGenres(aniData):
    def getAniGenre(data):
        mainAniData, aniUrl = data

        if isConnected():
            urlRequest = requests.get(aniUrl, headers=headers)

            if urlRequest.status_code == 200:
                content = urlRequest.content
                # print(getsizeof(content))

                if aniUrl.startswith("https://animedao.to"):
                    tree = bs4.BeautifulSoup(content, 'lxml')

                    genreHrefs = tree.find_all("a", {"class": "animeinfo_label"})

                    return [a.get("href", "").split("=")[-1] for a in genreHrefs]

                elif aniUrl.startswith("https://www1.gogoanime.cm"):
                    pattern = r"(<div class=\"anime_info_body_bg\">)\n((.|\n)*?)(\/div)"
                    matches = re.finditer(pattern, content.decode("utf-8"), re.MULTILINE)
                    adjContent = ""

                    for matchNum, match in enumerate(matches, start=1):
                        adjContent = match.group(2)

                    tree = bs4.BeautifulSoup(adjContent, 'lxml')

                    pTypeTags = tree.find_all("p", {"class": "type"})

                    genre = []
                    for pType in pTypeTags:
                        lowerText = pType.text.lower()

                        if "genre" in lowerText:
                            for aTag in pType.find_all("a"):
                                genre.append(aTag["title"])

                        elif "other name" in lowerText:
                            mainAniData["nameExtra"] = pType.text[12:]

                    return genre
        else:
            logging.info(f"Webscraper: Genre Sub - No Connection")

        return []

    if isConnected():
        with ThreadPoolExecutor(max_workers=min(20, max(len(aniData), 1))) as executor:
            results = executor.map(getAniGenre, [(data, data["ani"], ) for data in aniData])

        return [genre for genre in results]
    else:
        logging.info(f"Webscraper: Genre Main - No Connection")

    return []


def GetAniData(aniUrl):
    mode = aniUrl.startswith("https://www1.gogoanime.cm") and "gogoanime" or "animedao"
    baseUrl = mode == "animedao" and r"https://animedao.to" or r"https://www1.gogoanime.cm"

    if isConnected():
        urlRequest = requests.get(aniUrl, headers=headers)
        logging.info(f"Webscraper: Getting Ani Data - {aniUrl} - {mode}")

        if urlRequest.status_code == 200:
            content = urlRequest.content
            # print(getsizeof(content))

            tree = bs4.BeautifulSoup(content, 'lxml')

            if mode == "animedao":
                episodeHref = [a for a in tree.find_all("a") if "view" in a["href"]]
                episodeData = [[a["href"], a.find("div", {"class": "anime-title"})] for a in episodeHref]

                episodeData = [{"view": baseUrl + data[0], "title": data[1].text.strip(), "name": data[1].parent.find_all("span")[-1]["title"]} for data in episodeData if data[1].parent.find_all("span")[-1].get("title", "")]

                description = tree.find("div", {"id": "demo"}).text.strip()
                icon = baseUrl + tree.find("img")["src"]

                title = "-".join(tree.title.text.split("-")[:-1]).strip()

                aniUrlTitle = aniUrl.split("/")[-1]
                if aniUrlTitle[-1] == "/":
                    aniUrlTitle = aniUrlTitle[:-1]

                return title, icon, description, episodeData, aniUrlTitle, ""

            elif mode == "gogoanime":
                animeInfoTag = tree.find("div", {"class": "anime_info_body_bg"})
                title = animeInfoTag.find("h1").text.strip()
                icon = animeInfoTag.find("img")["src"]
                description = ""
                nameExtra = ""

                pTypeTags = tree.find_all("p", {"class": "type"})
                for pType in pTypeTags:
                    lowerText = pType.text.lower()

                    if "plot summary" in lowerText:
                        description = pType.text[14:]

                    if "other name" in lowerText:
                        nameExtra = pType.text[12:]

                episodePage = tree.find("ul", {"id": "episode_page"})
                episodeStartStops = [(aTag["ep_start"], aTag["ep_end"]) for aTag in episodePage.find_all("a")]

                episodeStartStops = [(int(start), int(end)) for start, end in episodeStartStops]

                startEp = min(map(min, episodeStartStops)) + 1
                maxEp = max(map(max, episodeStartStops))
                baseEpisodeUrl = f"{baseUrl}/{aniUrl.split('/')[-1]}-episode"

                episodeData = [{"view": f"{baseEpisodeUrl}-{i}", "title": f"{title} Episode {i}", "name": ""} for i in range(startEp, maxEp+1)]

                aniUrlTitle = aniUrl.split("/")[-1]
                if aniUrlTitle[-1] == "/":
                    aniUrlTitle = aniUrlTitle[:-1]

                return title, icon, description, episodeData, aniUrlTitle, nameExtra

    else:
        logging.info(f"Webscraper: Anime Info - No Connection")

    return None, None, None, None, None

def GetSourceSelenium(*args):
    def driverQuit(driver):
        driver.quit()

    chromePath, url, resultQueue, threadI = args[0]

    mainUA = generate_navigator_js()
    ua = mainUA["userAgent"]
    while "Trident" in ua:
        mainUA = generate_navigator_js()
        ua = mainUA["userAgent"]

    logging.info(f"Webscraper: SeleniumScrape{threadI} - UserAgent {ua} MainUserAgent {mainUA}")

    sS = time()
    service = Service(chromePath)
    if platform == "win":
        service.creationflags = CREATE_NO_WINDOW

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(f"--user-agent={ua}")
    # chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    # chrome_options.add_argument("--proxy-server='direct://'")
    # chrome_options.add_argument("--proxy-bypass-list=*")
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    eS = time() - sS

    s1 = time()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    eDriver = time() - s1

    s2 = time()

    sGet = time()
    driver.get(url)
    driver.switch_to.window(driver.window_handles[-1])
    eGet = time() - sGet

    sSearch = time()
    for _ in range(5):
        try:
            element = WebDriverWait(driver, 1).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "g-recaptcha"))
            )
            element.click()
        except:
            break

        sleep(0.1)

        try:
            driver.find_element(By.CLASS_NAME, "g-recaptcha")
        except NoSuchElementException:
            break
    else:
        logging.info(f"Webscraper: SeleniumScrape{threadI} - Exited Button Location Maturely")

    eSearch = time() - sSearch

    passed = True
    try:
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "rc"))
        )
    except:
        logging.info(f"Webscraper: SeleniumScrape{threadI} - Failed to Locate Video Data within TimeOut")
        passed = False

    if passed:
        source = driver.page_source
        if resultQueue:
            resultQueue.put([threadI, source])

    e1 = time() - s1
    e2 = time() - s2
    sQ = time()
    threading.Thread(target=driverQuit, args=(driver,), daemon=True).start()
    # driver.quit()
    eQ = time() - sQ
    logging.info(f"Webscraper: SeleniumScrape{threadI} - Total {e1} Get {eGet} Scrape {e2} Driver {eDriver} Settings {eS} Search {eSearch} Quit {eQ}")

    return source if passed else None


def extractVideoFiles(aniEpUrl, chromePath, repeat=5, currentRepeat=0):
    def getUrlProtocolDomain(url):
        urlParsed = urlparse(url)
        return urlParsed.scheme, urlParsed.netloc, urlParsed.path.split("/")[1]

    def recursiveGetVideoUrl(url, chromePath, finished=False, finalIndexOverride=None):
        newUrl = url
        logging.info(f"Webscraper: Requesting {url}")

        if not finished:
            if "sbplay2" in url and "/e/" in url:
                newUrl = url.replace("/e/", "/d/") + ".html"

            else:
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

                    elif urlDomain == "sbplay2.com" or urlDomain == "sbplay2.xyz":
                        if urlBasePath == "d":
                            aTags = tree.find_all("a", {"href": "#"})
                            functionCalls = [aTag.get("onclick") for aTag in aTags if aTag.get("onclick")]
                            functionMatches = [re.search("download_video\('(.*?)','(.*?)','(.*?)'\)", call) for call in functionCalls]
                            functionParams = [(match.group(1), match.group(2), match.group(3)) for match in functionMatches]

                            downloadInfo = [aTag.parent.parent.find_all("td")[1].text for aTag in aTags if aTag.get("onclick")]

                            #functionParam = functionParams[finalIndexOverride or -1]

                            #print(functionParams)

                            finished = True
                            links = [f"{urlScheme}://{urlDomain}/dl?op=download_orig&id={functionParam[0]}&mode={functionParam[1]}&hash={functionParam[2]}" for functionParam in functionParams]

                            s = time()

                            threads = []

                            results = queue.Queue()

                            for i, link in enumerate(links):
                                thread = threading.Thread(target=GetSourceSelenium, args=((chromePath, link, results, i),))
                                threads.append(thread)
                                # GetSource(chromePath, url, results)

                            for thread in threads:
                                thread.start()

                            for thread in threads:
                                thread.join()

                            #newUrl = [recursiveGetVideoUrl(]

                            unsyncSourcesData = list(results.queue)
                            sources = [""] * len(downloadInfo)
                            for sourceData in unsyncSourcesData:
                                sources[sourceData[0]] = sourceData[1]

                            """
                            a
                            with Pool(len(links)) as p:
                                sources = p.map(GetSourceSelenium, [(chromePath, link, None,) for link in links])
                            """

                            e = time() - s
                            logging.info(f"Webscraper: SeleniumTotal {e}")

                            regex = r"<a href=\"(.*?)\">Direct Download Link<\/a>"
                            searches = [re.search(regex, source) for source in sources]
                            links = [search.group(1) if search else "NA" for search in searches]
                            newUrl = list(zip(links, downloadInfo))

                            if all([link == "NA" for link in links]):
                                newUrl = "empty"

                            finished = True

                        elif urlBasePath == "dl":
                            if not tree.find("b", {"class": "err"}):
                                aTags = tree.find_all("a")
                                downloadA = [aTag["href"] for aTag in aTags if aTag.text == "Direct Download Link"][0]

                                newUrl = downloadA
                                finished = True

                                #print("FINISHED", newUrl)

                        elif urlBasePath == "e":
                            newUrl = url.replace("/e/", "/d/")

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
                    logging.info(f"Webscraper: Failed to Request {urlRequest.status_code}")
                    newUrl = "empty"
                    finished = True

        if finished:
            logging.info("Webscraper: --------------------------------------------")
            pass

        return finished and newUrl or recursiveGetVideoUrl(newUrl, chromePath)

    #aniEpUrl = r"https://animedao.to/view/431131313/"
    mode = aniEpUrl.startswith("https://www1.gogoanime.cm") and "gogoanime" or "animedao"
    baseUrl = r"https://animedao.to"

    if isConnected():
        urlRequest = requests.get(aniEpUrl, headers=headers)
        logging.info(f"Webscraper: Scanning {aniEpUrl}")

        if urlRequest.status_code == 200:
            logging.info(f"Webscraper: Scanning - In Progress")

            content = urlRequest.content
            # print(getsizeof(content))

            tree = bs4.BeautifulSoup(content, 'lxml')
            sources = []

            if mode == "animedao":
                scripts = tree.find_all("script")
                scripts = [script.text for script in scripts if "/redirect/" in script.text or "playdrive.xyz" in script.text]
                iframes = [re.search("<iframe (.*?)</iframe>", script) for script in scripts]
                iframes = [iframeRe.group() for iframeRe in iframes if iframeRe]

                sources = [re.search(r'src\s*=\s*"(.+?)"', iframe).group(1) for iframe in iframes]
                sources = ["redirect" in source and baseUrl + source or source for source in sources]

            elif mode == "gogoanime":
                sources = [tree.find("li", {"class", "dowloads"}).find("a")["href"]]
                sources.extend([aTag["data-video"] for aTag in tree.find_all("a") if aTag.has_attr("data-video") and "sbplay2" in aTag["data-video"]])

            urls = []
            for url in sources:
                endUrl = recursiveGetVideoUrl(url, chromePath)
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

    else:
        logging.info(f"Webscraper: Video Extracter - No Connection")

    return []


if __name__ == "__main__":
    from time import time

    s = time()
    data2 = extractVideoFiles(r"https://animedao.to/view/4704419159/")
    print(data2)
    e = time() - s

    print(f"{round(e*1000)}ms")

    #SearchDataAnimeDaoTo("Sword Art Online")
