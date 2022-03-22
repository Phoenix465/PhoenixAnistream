import os

from webdriver_manager.chrome import ChromeDriverManager

try:
    os.mkdir("logs")
except:
    pass

from kivy.config import Config
Config.set('kivy', 'exit_on_escape', '0')
Config.set('kivy', 'window_icon', 'resources\PhoenixAniStream.png')
Config.set('kivy', 'log_dir', os.path.join(os.path.split(os.path.abspath(__file__))[0], "logs"))
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('graphics', 'minimum_width', '320')
Config.set('graphics', 'minimum_height', '180')

import atexit
import logging
import queue
import threading
import webbrowser
import copy

import kivy
from kivy.storage.jsonstore import JsonStore
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

kivy.require('2.0.0')  # replace with your current kivy version !

from kivy.core.window import Window
#Window.size = (1280 / 2, 720 / 2)

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import NumericProperty, BooleanProperty, StringProperty
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.factory import Factory

import os.path as path
from os import mkdir
from KivyOnTop import register_topmost, unregister_topmost

# from kivy.loader import Loader
# Loader.loading_image = "loading.gif"

from math import ceil
import requests
from concurrent.futures import ThreadPoolExecutor

import webscraper
import sys
from time import time, sleep

from pypresence import Presence

# Back up the reference to the exceptionhook
sys._excepthook = sys.excepthook


def my_exception_hook(exctype, value, traceback):
    # Print the error and traceback
    print(exctype, value, traceback)
    # Call the normal Exception hook after
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


# Set the exception hook to our wrapping function
sys.excepthook = my_exception_hook


def GetDataStore(DataStore, key, default=None, writeDefaultIfNotExists=False):
    if key in DataStore:
        return DataStore[key]
    else:
        return default


class AniWidget(RelativeLayout):
    pass


class SearchAniWidget(RelativeLayout):
    pass


class WindowManager(ScreenManager):
    pass


class EpisodeWidget(RelativeLayout):
    pass


class VideoInfo(Button):
    pass


class TempInputBox(TextInput):
    def insert_text(self, substring, from_undo=False):
        substring = "".join([char for char in substring if char in "0123456789"])
        new = self.text + substring

        if new != "" and int(new) > self.parent.maxEp:
            substring = ""

        return super(TempInputBox, self).insert_text(substring, from_undo=from_undo)


class LongShortPressButton(Factory.Button):
    __events__ = ('on_long_press', 'on_short_press', )

    long_press_time = Factory.NumericProperty(1)
    
    downClickTime = time()
    debounce = True
    
    def on_state(self, instance, value):
        if value == 'down' and self.debounce:
            self.debounce = False
            self.downClickTime = time()
            lpt = self.long_press_time
            self._clockev = Clock.schedule_once(self._do_long_press, lpt)
            
        elif not self.debounce:  # value == "up"
            if time() - self.downClickTime < self.long_press_time:                
                self._do_short_press(0)

            self.debounce = True   
            self._clockev.cancel()

    def _do_long_press(self, dt):
        self.dispatch('on_long_press')
    
    def _do_short_press(self, dt):
        self.dispatch('on_short_press')
    
    def on_long_press(self, *largs):
        pass
    
    def on_short_press(self, *largs):
        pass


class DiscordRichPresenceHandler:
    def __init__(self):
        clientId = 955889481960013888

        self.RPC = None

        if platform == "win":
            self.RPC = Presence(clientId)
            self.RPC.connect()

    def update(self, title, state, time):
        if self.RPC:
            self.RPC.update(
                large_image="phoenixanistreamlarge",
                large_text="Phoenix Anistream",
                small_image="whitecircle",
                small_text="v1.0.6",
                details=title,
                state=state,
                start=time
            )


class HomeWindow(Widget):
    padding = NumericProperty(20)
    spacingX = NumericProperty(10)
    imageSizeYOrig = 0.8
    imageSizeY = NumericProperty(0.8)
    fontSize = NumericProperty(10)
    aniWidgetWidth = NumericProperty(Window.size[1] * 0.3)
    aniWidgetHeight = NumericProperty(Window.size[1] * 0.3 * 16 / 9)
    aniWidgetHeightExtra = NumericProperty(0)
    gridCols = NumericProperty(1)

    oldScreensize = Window.size

    searchToggle = BooleanProperty(False)

    firstUpdateAniWidget = False

    ScrollAniGrid = None
    ScrollSearchGrid = None
    ScrollRecentGrid = None
    ScrollBookmarkGrid = None

    NoAnimeFound = None

    MainScrollGrid = None
    OtherMainScrollGrid = None
    videoWindow = None

    bookmarkMode = False

    OldSearchText = ""

    searchQueue = queue.LifoQueue()
    latestSearchThread = None

    infoWindowWidget = None

    oldRecentWatch = {}
    oldBookmarkedAni = {}

    dRPC = None

    # --- Ani Data Updater ---
    def updateVars(self, dt):
        width, height = Window.size
        self.aniWidgetWidth = height * 0.3
        self.aniWidgetHeight = height * 0.3 * 16 / 9

        self.gridCols = round(width // (height * 0.3 + 20))
        self.spacingX = (width - self.padding - self.padding - self.gridCols * self.aniWidgetWidth) / max(1,
                                                                                                          self.gridCols - 1)

        self.fontSize = height / 36

    def updateAniWidgets(self, dt, override=False):
        currentScreensize = Window.size

        searchBox = self.ids.TextInputSearchBox

        #gridLayout = (self.ScrollAniGrid == self.MainScrollGrid and self.ids.AniGridLayout or self.ids.RecentGridLayout) if searchBox.opacity == 0 else self.ids.SearchGridLayout
        if self.ScrollAniGrid.parent == self:
            gridLayout = self.ids.AniGridLayout
        elif self.ScrollSearchGrid.parent == self:
            gridLayout = self.ids.SearchGridLayout
        elif self.ScrollRecentGrid.parent == self:
            gridLayout = self.ids.RecentGridLayout
        elif self.ScrollBookmarkGrid.parent == self:
            gridLayout = self.ids.BookmarkGridLayout
        else:
            print("Error Grid Layout")
            return

        #gridLayout = (self.ScrollAniGrid == self.MainScrollGrid and self.ids.AniGridLayout or self.ids.RecentGridLayout) if searchBox.opacity == 0 else self.ids.SearchGridLayout
        gridLayout.height = gridLayout.minimum_height

        if currentScreensize != self.oldScreensize or not self.firstUpdateAniWidget or override:
            self.firstUpdateAniWidget = True
            self.SearchButtonToggle(skip=True)
            self.searchInputChanged(reload=True)

            maxRows = 0
            for child in gridLayout.children:
                text = child.ids.AniLabelButton.text
                textS = text.split("\n")
                # text = "\n".join(textS[:-1])

                rowsPLengths = [len(t) * self.fontSize * 0.55 for t in textS]
                rowsLengths = [ceil(pLength / self.aniWidgetWidth) for pLength in rowsPLengths]

                rows = sum(rowsLengths)
                rows += 2

                # print(textS, rowsLengths)

                if rows > maxRows:
                    maxRows = rows

                    # print(maxRows, textS, rowsLengths)

            self.aniWidgetHeightExtra = maxRows * (self.fontSize * 1.1) - (
                        1 - self.imageSizeYOrig) * self.aniWidgetHeight / 2
            self.imageSizeY = (self.imageSizeYOrig * self.aniWidgetHeight) / (
                        self.aniWidgetHeight + self.aniWidgetHeightExtra)

            # print(repr(text))

            for child in gridLayout.children:
                child.height = self.aniWidgetHeight + self.aniWidgetHeightExtra
                child.width = self.aniWidgetWidth
                child.fontSize = self.fontSize
                child.ids.AniLabelButton.text = child.ids.AniLabelButton.text

                child.imageSizeY = self.imageSizeY

            scrollView = self.ids.ScrollAniGrid
            scrollView.size = (currentScreensize[0], currentScreensize[1]*0.9)
            scrollView.size_hint = (1, None)

        self.oldScreensize = currentScreensize

    @mainthread
    def showGenerateData(self):
        gridLayout = self.ids.AniGridLayout

        threadData = []

        for aniData in self.latestAniData:
            thumbnailUrl = aniData["thumbnail"]

            widget = AniWidget(width=self.aniWidgetWidth,
                               height=self.aniWidgetHeight,
                               thumbnailUrl=thumbnailUrl,
                               aniText=aniData["name"],
                               imageSizeY=self.imageSizeY,
                               episodeNumber=aniData["episode"],
                               fontSize=self.fontSize,
                               data=aniData)

            gridLayout.add_widget(widget)

            threadData.append((widget.ids.Thumbnail, thumbnailUrl))

        self.updateAniWidgets(0, override=True)
        threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True).start()

    def grabData(self):
        self.latestAniData = webscraper.GetLatestDataAnimeDaoTo()
        self.showGenerateData()

    def updateLatestAniData(self, dt):
        gridLayout = self.ids.AniGridLayout
        gridLayout.remove_widget(self.ids.PlaceHolder)

        threading.Thread(target=self.grabData, daemon=True).start()

    def updateImageTexture(self, data):
        image, url = data
        fileName = url.split("/")[-1]
        filePath = path.join("cache", fileName)

        if not path.isfile(filePath):
            if webscraper.isConnected():
                request = requests.get(url)
                if request.ok:
                    content = request.content
                    file = open(filePath, "wb")
                    file.write(content)
                    file.close()

                    self.loadImageTexture(image, filePath)
            else:
                logging.info("Image Downloader: Download Failed - No Connection")
        else:
            self.loadImageTexture(image, filePath)

    @mainthread
    def loadImageTexture(self, image, filePath):
        image.source = filePath
        image.reload()

    def updateImageTextures(self, values):
        # return

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(self.updateImageTexture, values)

        for result in results:
            force = result  # Generating Result :)

    def runSearchQueue(self, *args):
        if self.searchQueue.not_empty:
            thread = self.searchQueue.get()
            thread.start()

            self.latestSearchThread = thread

    def setWidget(self, dt):
        self.ScrollSearchGrid = self.ids.ScrollSearchGrid.__self__
        self.ScrollAniGrid = self.ids.ScrollAniGrid.__self__
        self.ScrollRecentGrid = self.ids.ScrollRecentGrid.__self__
        self.ScrollBookmarkGrid = self.ids.ScrollBookmarkGrid.__self__
        self.NoAnimeFound = self.ids.NoAnimeFound.__self__

        self.MainScrollGrid = self.ids.ScrollAniGrid.__self__
        self.OtherMainScrollGrid = self.ids.ScrollRecentGrid.__self__

        gridLayout = self.ids.RecentGridLayout
        gridLayout.clear_widgets()

        self.remove_widget(self.ids.PlaceHolder)
        self.remove_widget(self.ids.PlaceHolder2)
        self.remove_widget(self.ids.PlaceHolder3)
        self.remove_widget(self.ids.PlaceHolder4)
        self.remove_widget(self.ScrollSearchGrid)
        self.remove_widget(self.ScrollRecentGrid)
        self.remove_widget(self.ScrollBookmarkGrid)
        self.remove_widget(self.NoAnimeFound)

        searchBox = self.ids.TextInputSearchBox
        searchBox.bind(text=self.searchInputChanged)

        # Fixes weird clipping issue on name label when using screen manager...
        self.remove_widget(self.ScrollAniGrid)
        self.add_widget(self.ScrollSearchGrid)
        self.add_widget(self.ScrollRecentGrid)
        self.add_widget(self.ScrollBookmarkGrid)
        self.add_widget(self.NoAnimeFound)

        self.add_widget(self.ScrollAniGrid)
        self.remove_widget(self.ScrollSearchGrid)
        self.remove_widget(self.ScrollRecentGrid)
        self.remove_widget(self.ScrollBookmarkGrid)
        self.remove_widget(self.NoAnimeFound)

        # self.SearchButtonToggle()
        # self.SearchButtonToggle()

    def searchData(self, searchQuery):
        @mainthread
        def addWidgets(searchData, genreData):
            threadData = []

            showCrying = True
            for i, data in enumerate(searchData):
                showCrying = False

                thumbnailUrl = data["thumbnail"]

                rawNameExtra = data["nameExtra"]
                if len(data["nameExtra"]) > 17:
                    data["nameExtra"] = data["nameExtra"][:17] + "..."

                widget = SearchAniWidget(
                    width=self.aniWidgetWidth,
                    height=self.aniWidgetHeight,
                    thumbnailUrl=thumbnailUrl,
                    aniText=data["name"],
                    genre=", ".join(genreData[i]),
                    imageSizeY=self.imageSizeY,
                    extraNames=data["nameExtra"],
                    rawExtraNames=rawNameExtra,
                    fontSize=self.fontSize,
                    data=data
                )

                gridLayout.add_widget(widget)

                threadData.append((widget.ids.Thumbnail.__self__, thumbnailUrl))

            if showCrying and self.NoAnimeFound.parent != self and self.ScrollSearchGrid.parent == self :
                self.add_widget(self.NoAnimeFound)
            elif not showCrying and self.NoAnimeFound.parent == self:
                self.remove_widget(self.NoAnimeFound)

            self.updateAniWidgets(0, override=True)

            updateThread = threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True)
            updateThread.start()
            threading.Thread(target=self.runSearchQueue, daemon=True).start()

        if self.NoAnimeFound.parent == self:
            self.remove_widget(self.NoAnimeFound)

        gridLayout = self.ids.SearchGridLayout
        gridLayout.clear_widgets()

        searchData = webscraper.SearchDataAnimeDaoTo(searchQuery)
        genreData = webscraper.GetAniGenres(searchData)

        if self.searchQueue.qsize() > 0:
            threading.Thread(target=self.runSearchQueue, daemon=True).start()
        else:
            addWidgets(searchData, genreData)

    def searchInputChanged(self, *args, reload=False):
        searchBox = self.ids.TextInputSearchBox
        searchQuery = searchBox.text

        #print("WARNING WARNING")
        #self.parent.manager.transition.direction = 'down'
        #self.parent.manager.current = "VideoPlayer"

        if searchBox.opacity == 1 and self.OldSearchText != searchQuery:
            self.OldSearchText = searchQuery

            if not self.bookmarkMode:
                if len(searchQuery) >= 3:
                    if self.MainScrollGrid.parent == self:
                        self.remove_widget(self.MainScrollGrid)
                    if self.OtherMainScrollGrid.parent == self:
                        self.remove_widget(self.OtherMainScrollGrid)

                    if self.ScrollSearchGrid.parent != self:
                        self.add_widget(self.ScrollSearchGrid)
                    if self.ScrollBookmarkGrid.parent == self:
                        self.remove_widget(self.ScrollBookmarkGrid)

                    self.ids.HistoryButton.opacity = 0
                    self.ids.HistoryButton.disabled = True

                    if not reload:
                        with self.searchQueue.mutex:
                            self.searchQueue.queue.clear()

                        thread = threading.Thread(target=self.searchData, args=(searchQuery,), daemon=True)
                        self.searchQueue.put(thread)

                        if self.searchQueue.qsize() == 1 and not (
                                self.latestSearchThread and self.latestSearchThread.is_alive):
                            self.runSearchQueue()

                else:
                    if self.MainScrollGrid.parent != self:
                        self.add_widget(self.MainScrollGrid)
                    if self.OtherMainScrollGrid.parent == self:
                        self.remove_widget(self.OtherMainScrollGrid)

                    if self.ScrollSearchGrid.parent == self:
                        self.remove_widget(self.ScrollSearchGrid)
                    if self.ScrollBookmarkGrid.parent == self:
                        self.remove_widget(self.ScrollBookmarkGrid)

                    if self.NoAnimeFound.parent == self:
                        self.remove_widget(self.NoAnimeFound)

                    self.ids.HistoryButton.opacity = 1
                    self.ids.HistoryButton.disabled = False
            else:
                if self.MainScrollGrid.parent == self:
                    self.remove_widget(self.MainScrollGrid)
                if self.OtherMainScrollGrid.parent == self:
                    self.remove_widget(self.OtherMainScrollGrid)
                if self.ScrollSearchGrid.parent == self:
                    self.remove_widget(self.ScrollSearchGrid)

                if self.ScrollBookmarkGrid.parent != self:
                    self.add_widget(self.ScrollBookmarkGrid)

                self.ids.HistoryButton.opacity = 0
                self.ids.HistoryButton.disabled = True

                self.RefreshBookmarkedAni(searchQuery=searchQuery, override=True)

    def RefreshRecentlyWatched(self, *args):
        storedData = JsonStore("data.json")
        recentlyWatchedData = GetDataStore(storedData, "RecentlyWatched", default={})

        if self.oldRecentWatch != recentlyWatchedData:
            self.oldRecentWatch = recentlyWatchedData

            gridLayout = self.ids.RecentGridLayout
            gridLayout.clear_widgets()

            rawData = []

            # To Prevent Object Linking when appending name to the epData location
            for name, aniEpsData in copy.deepcopy(self.oldRecentWatch).items():
                for _, epData in aniEpsData.items():
                    if not epData[7]:
                        epData.append(name)
                        rawData.append(epData)

            rawData = sorted(rawData, key=lambda data: data[0], reverse=True)
            threadData = []

            for data in rawData:
                epNum = 0
                try:
                    epNum = float(data[2])
                    epNum = int(epNum)
                except:
                    pass

                widget = AniWidget(width=self.aniWidgetWidth,
                                   height=self.aniWidgetHeight,
                                   thumbnailUrl=data[3],
                                   aniText=data[1],
                                   imageSizeY=self.imageSizeY,
                                   episodeNumber=epNum,
                                   fontSize=self.fontSize,
                                   restoreLink=data[4],
                                   specialData=data)

                gridLayout.add_widget(widget)

                threadData.append((widget.ids.Thumbnail, data[3]))

            self.updateAniWidgets(0, override=True)
            self.RefreshBookmarkedAni(override=True)
            threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True).start()

    def RefreshBookmarkedAni(self, *args, searchQuery="", override=False):
        storedData = JsonStore("data.json")
        recentlyBookmarkedAni = GetDataStore(storedData, "BookmarkData", default={})
        aniData = GetDataStore(storedData, "AniData", default={})
        recentlyWatched = GetDataStore(storedData, "RecentlyWatched", default={})

        searchQuerySplit = searchQuery.lower().split(" ")
        if self.oldBookmarkedAni != recentlyBookmarkedAni or override:
            self.oldBookmarkedAni = recentlyBookmarkedAni

            if self.NoAnimeFound.parent == self:
                self.remove_widget(self.NoAnimeFound)

            gridLayout = self.ids.BookmarkGridLayout
            gridLayout.clear_widgets()

            threadData = []
            showCrying = True
            for bookmarkName, bookmarkData in self.oldBookmarkedAni.items():
                overallSearch = (bookmarkData[2] + bookmarkData[4]).lower()

                if not bookmarkData[0] or not all(query in overallSearch for query in searchQuerySplit):
                    continue

                showCrying = False

                maxEp = aniData[bookmarkName][0] if bookmarkName in aniData else 0
                watchedData = recentlyWatched[bookmarkName] if bookmarkName in recentlyWatched else {}

                widget = SearchAniWidget(
                    width=self.aniWidgetWidth,
                    height=self.aniWidgetHeight,
                    thumbnailUrl=bookmarkData[1],
                    aniText=bookmarkData[2],
                    genre="",
                    imageSizeY=self.imageSizeY,
                    extraNames=f"{len(watchedData.keys())}/{maxEp}",
                    fontSize=self.fontSize,
                    data={"ani": bookmarkData[3]}
                )

                gridLayout.add_widget(widget)

                threadData.append((widget.ids.Thumbnail.__self__, bookmarkData[1]))

            if searchQuery == "":
                showCrying = False

            if self.ScrollBookmarkGrid.parent == self:
                if showCrying and self.NoAnimeFound.parent != self:
                    self.add_widget(self.NoAnimeFound)
                elif not showCrying and self.NoAnimeFound.parent == self:
                    self.remove_widget(self.NoAnimeFound)

            threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True).start()

            self.updateAniWidgets(0, override=True)

    # --- Callback Methods ---
    def AboutButtonClicked(self):
        size = Window.size

        button = Button(
            text='Phoenix Anistream is an anime streaming app that allows users to search and watch anime. There are no ads and interruptions. Have Fun :)'
                 '\n\n[color=#8AB4F8][i][u][ref=https://discord.gg/MycXAEfcRr]Phoenix Anistream Support Server[/ref][/u][/i][/color]'
                 '\n\nClick Button To Close',
            markup=True,
            font_size=size[1]/22
            # size_hint=(0.6, 1),
        )

        def refPress(instance, val):
            webbrowser.open(val)

        button.bind(on_ref_press=refPress)

        def setButtonTextSize(instance, size):
            instance.text_size[0] = size[0] * 0.9

        button.bind(size=setButtonTextSize)
        popup = Popup(title='About',
                      content=button,
                      size_hint=(0.8, 0.8),
                      auto_dismiss=True)
        button.bind(on_release=popup.dismiss)
        popup.open()

    def HistoryButtonClicked(self):
        if self.MainScrollGrid.parent == self:
            self.remove_widget(self.MainScrollGrid)
            self.add_widget(self.OtherMainScrollGrid)

        self.MainScrollGrid, self.OtherMainScrollGrid = self.OtherMainScrollGrid, self.MainScrollGrid
        self.ids.HistoryButton.clicked = self.MainScrollGrid == self.ScrollRecentGrid

        if self.ids.HistoryButton.clicked and self.ids.ViewBookmarkButton.clicked:
            self.ViewBookmarkButtonToggle()

        self.updateAniWidgets(0, override=True)

    def ViewBookmarkButtonToggle(self, override=False):
        if not override:
            self.bookmarkMode = not self.bookmarkMode

        self.ids.ViewBookmarkButton.clicked = self.bookmarkMode

        if self.ids.HistoryButton.clicked and self.ids.ViewBookmarkButton.clicked:
            self.HistoryButtonClicked()

        self.RefreshBookmarkedAni(override=True)
            
        if self.bookmarkMode:
            if self.MainScrollGrid.parent == self:
                self.remove_widget(self.MainScrollGrid)
            if self.OtherMainScrollGrid.parent == self:
                self.remove_widget(self.OtherMainScrollGrid)
            if self.ScrollSearchGrid.parent == self:
                self.remove_widget(self.ScrollSearchGrid)
            if self.ScrollBookmarkGrid.parent != self:
                self.add_widget(self.ScrollBookmarkGrid)

        else:
            if self.MainScrollGrid.parent != self:
                self.add_widget(self.MainScrollGrid)
            if self.OtherMainScrollGrid.parent == self:
                self.remove_widget(self.OtherMainScrollGrid)
            if self.ScrollSearchGrid.parent != self:
                self.remove_widget(self.ScrollSearchGrid)

            if self.ScrollBookmarkGrid.parent == self:
                self.remove_widget(self.ScrollBookmarkGrid)

            if self.NoAnimeFound.parent == self:
                self.remove_widget(self.NoAnimeFound)

        self.ids.HistoryButton.opacity = 1
        self.ids.HistoryButton.disabled = False

        self.SearchButtonToggle(overrideValue=False)
        self.updateAniWidgets(0, override=True)

    def SearchButtonToggle(self, skip=False, overrideValue=None):
        if not skip:
            self.searchToggle = not self.searchToggle

        if overrideValue is not None:
            self.searchToggle = overrideValue
            skip = True

        duration = 0 if skip else 0.2

        titleNameWidget = self.ids.Title
        searchBox = self.ids.TextInputSearchBox
        searchButton = self.ids.SearchButton
        backButton = self.ids.BackButton

        if not skip:
            if not self.searchToggle:
                self.bookmarkMode = False
                self.ViewBookmarkButtonToggle(override=True)

                if self.NoAnimeFound.parent == self:
                    self.remove_widget(self.NoAnimeFound)

        if not skip:
            if self.searchToggle:
                searchBox.text = ""

            else:
                if self.MainScrollGrid.parent != self:
                    self.add_widget(self.MainScrollGrid)
                if self.OtherMainScrollGrid.parent == self:
                    self.remove_widget(self.OtherMainScrollGrid)

                if self.ScrollSearchGrid.parent == self:
                    self.remove_widget(self.ScrollSearchGrid)

                self.ids.HistoryButton.opacity = 1
                self.ids.HistoryButton.disabled = False

        size = Window.size

        if self.searchToggle:
            searchButton.disabled = True
            searchButton.opacity = 0

            backButton.disabled = False
            backButton.opacity = 1

            titleAnim = Animation(x=-size[0] / 2 - (size[1] * 0.1 * 0.4) * len(titleNameWidget.text) / 2 * 0.6,
                                  duration=duration)
            titleAnim.start(titleNameWidget)

            searchBoxAnim = Animation(x=size[0] * 0.075, width=size[0] * 0.75, opacity=1, duration=duration)
            searchBoxAnim.start(searchBox)
            searchBox.readonly = False
        else:
            searchButton.disabled = False
            searchButton.opacity = 1

            backButton.disabled = True
            backButton.opacity = 0

            titleAnim = Animation(x=-size[0] / 2 + (size[1] * 0.1 * 0.4) * len(titleNameWidget.text) / 2 * 0.6,
                                  duration=duration)
            titleAnim.start(titleNameWidget)

            searchBoxAnim = Animation(x=size[0] * (0.75+0.075), width=0, opacity=0, duration=duration)
            searchBoxAnim.start(searchBox)
            searchBox.readonly = True

    def AniSearchButtonPressed(self, instance):
        if instance.data:
            self.parent.manager.transition.direction = 'down'
            self.parent.manager.current = "AniInfoWindow"

            self.dRPC.update("Idle", None, None)

            self.infoWindowWidget.generateAniData(instance.data["ani"], instance.rawExtraNames)

        elif instance.restoreLink:
            self.parent.manager.transition.direction = 'down'
            self.parent.manager.current = "VideoPlayer"

            data = instance.specialData

            #self.dRPC.update(f"Watching {data[1]}", f"Episode {instance.episodeNumber}", int(time()))

            self.videoWindow.initiate(EpisodeWidget(
                episodeNumber=str(instance.episodeNumber),
                title=f"{data[1]} Episode {instance.episodeNumber}",
                name=data[1],
                colour="#ffffff",
                view=data[4],
                aniTitle=data[-1],
                thumbnailSource=data[3],
                aniTitleGood=data[1],
                aniUrl=data[5], 
                maxEpNum=data[6]
            ), recentBypass=True)


class InfoWindow(Widget):
    aniName = StringProperty("")

    epWidgetWidth = NumericProperty(Window.size[1] * 0.1)
    epWidgetHeight = NumericProperty(Window.size[1] * 0.1)

    gridCols = NumericProperty(5)
    spacingX = NumericProperty(20)

    placeholderExists = True
    aniRawName = ""
    aniUrl = ""
    extraNames = ""

    videoWindow = None
    aniData = None

    dRPC = None

    def BackArrowPressed(self):
        self.parent.manager.transition.direction = 'up'
        self.parent.manager.current = "MainWindow"

        self.dRPC.update(f"Idle", None, None)

        self.ids.description.textDescription = ""
        self.ids.EpisodeGridLayout.clear_widgets()
        self.aniName = ""
        self.ids.Thumbnail.source = "resources/loading.gif"

        self.aniRawName = ""
        self.extraNames = ""
        self.aniData = None

        self.ids.BookmarkButton.clicked = False
        self.ids.EpisodeCounter.text = "0/0"
        
    def updateImageTexture(self, data):
        image, url = data
        fileName = url.split("/")[-1]
        filePath = path.join("cache", fileName)

        if not path.isfile(filePath):
            if webscraper.isConnected():
                request = requests.get(url)
                if request.ok:
                    content = request.content
                    file = open(filePath, "wb")
                    file.write(content)
                    file.close()

                    self.loadImageTexture(image, filePath)
            else:
                logging.info("Image Downloader: Download Failed - No Connection")
        else:
            self.loadImageTexture(image, filePath)

    @mainthread
    def loadImageTexture(self, image, filePath):
        image.source = filePath
        image.reload()

    def updateImageTextures(self, values):
        # return

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(self.updateImageTexture, values)

        for result in results:
            force = result  # Generating Result :)

    def updateVars(self, *args):
        width, height = Window.size

        self.epWidgetWidth = height * 0.1
        self.epWidgetHeight = height * 0.1

        self.gridCols = round((width * 0.8) // (self.epWidgetWidth + 20))
        self.spacingX = ((width * 0.8) - 20 - 20 - self.gridCols * self.epWidgetWidth) / max(1, self.gridCols - 1)

        episodeGridLayout = self.ids.EpisodeGridLayout
        for child in episodeGridLayout.children:
            child.height = self.epWidgetHeight
            child.width = self.epWidgetWidth
            child.fontSize = height / 24

    def refreshDescription(self, *args):
        width, height = Window.size

        descriptionId = self.ids.description

        text = descriptionId.textDescription
        textS = text.split("\n")

        rowsPLengths = [len(t) * (height / 24) * 0.55 for t in textS]
        rowsLengths = [ceil(pLength / ((1 - 0.05 * 2) * width)) for pLength in rowsPLengths]

        rows = sum(rowsLengths)
        rows += 1

        adjHeight = rows * height / 24

        episodeGridLayout = self.ids.EpisodeGridLayout
        episodeGridLayout.y = 0

        episodeInput = self.ids.EpisodeInput
        episodeInput.y = episodeGridLayout.minimum_height + (0.05 * height)
        episodeInput.maxEp = len(episodeGridLayout.children)

        episodeInputInput = episodeInput.ids.EpisodeInputInput
        episodeInputInput.hint_text = f"Episode No between 1 to {episodeInput.maxEp}"

        descriptionId.descriptionHeight = adjHeight
        descriptionId.descriptionHeightOffset = episodeInput.y + episodeInput.height + (0.05 * height)

        thumbnail = self.ids.Thumbnail

        episodeCounter = self.ids.EpisodeCounter
        episodeCounter.y = thumbnail.y - (0.05 * height) - episodeCounter.height

        bookmarkButton = self.ids.BookmarkButton
        bookmarkButton.y = thumbnail.y - (0.05 * height) - bookmarkButton.height

        self.ids.RelLayout.height = episodeGridLayout.minimum_height + \
                                    episodeInput.height + \
                                    descriptionId.height + \
                                    episodeCounter.height + \
                                    self.ids.Thumbnail.height + (
                    0.05 * 4 * height)
        episodeGridLayout.y = 0

        self.updateVars()

    def searchClicked(self):
        episodeGridLayout = self.ids.EpisodeGridLayout
        scrollSearchGrid = self.ids.ScrollSearchGrid
        episodeInput = self.ids.EpisodeInput

        for widget in episodeGridLayout.children:
            if int(widget.ids.ButtonWidget.text or '-1') == int(episodeInput.ids.EpisodeInputInput.text or '-2'):
                scrollSearchGrid.scroll_to(widget)

    def BookmarkClicked(self, refresh=False):
        storedData = JsonStore("data.json")
        bookmarkData = GetDataStore(storedData, "BookmarkData", default={})

        bookmarkInfo = self.aniRawName in bookmarkData and bookmarkData[self.aniRawName] or [False, self.aniData[1], self.aniData[0], self.aniUrl, self.extraNames, time()]
        bookmarkInfo[5] = time()

        if not refresh:
            bookmarkInfo[0] = not bookmarkInfo[0]

        bookmarkData[self.aniRawName] = bookmarkInfo

        if not bookmarkInfo[0]:
            del bookmarkData[self.aniRawName]

        storedData["BookmarkData"] = bookmarkData

        self.ids.BookmarkButton.clicked = bookmarkInfo[0]

    def generateAniData(self, aniUrl, extraNames):
        def loadAniData(url):
            data = webscraper.GetAniData(aniUrl)
            self.aniData = data

            episodeGridLayout = self.ids.EpisodeGridLayout
            episodeGridLayout.clear_widgets()

            if not any(data):
                return

            self.aniName = data[0]
            self.aniRawName = data[4]
            self.extraNames = self.extraNames or data[5]

            descriptionId = self.ids.description
            descriptionId.textDescription = data[2]
            self.refreshDescription()

            if self.placeholderExists:
                try:
                    episodePlaceHolder = self.ids.EpisodePlaceHolder
                    episodeGridLayout.remove_widget(episodePlaceHolder)
                except:
                    pass

                self.placeholderExists = False

            titleAlready = []

            movies = 0
            special = 0
            extra = 0

            epData = []

            storedData = JsonStore("data.json")
            recentlyWatchedData = GetDataStore(storedData, "RecentlyWatched", default={})
            aniRecentData = recentlyWatchedData[data[4]] if data[4] in recentlyWatchedData else {}

            aniData = GetDataStore(storedData, "AniData", default={})
            aniData[data[4]] = [len(data[3])]
            storedData["AniData"] = aniData

            self.BookmarkClicked(refresh=True)

            for episodeData in data[3]:
                # Not sure for this part..
                if True or self.aniName in episodeData["title"]:
                    adjTitle = episodeData["title"].replace(self.aniName, "").strip()
                    numberEp = adjTitle.lower().replace("episode", "").strip()

                    if numberEp not in titleAlready:
                        titleAlready.append(numberEp)

                        nameEpFilter = "".join([char for char in numberEp if char in "0123456789"])
                        special = "episode" not in adjTitle.lower()

                        mode = 0
                        colour = 0

                        if "special" in adjTitle.lower():
                            special += 1
                            mode = 1
                            colour = "#ffd700"

                        elif "movie" in adjTitle.lower():
                            movies += 1
                            mode = 2
                            colour = "#0AB4FC"

                        elif len(nameEpFilter) == 0:
                            extra += 1
                            mode = 3
                            nameEpFilter = str(extra)
                            colour = "#6a0dad"

                        elif "episode" not in adjTitle.lower():
                            special += 1
                            mode = 1
                            colour = "#ffd700"

                        else:
                            colour = "#555961"

                        episodeData["mode"] = mode
                        episodeData["colour"] = colour
                        episodeData["number"] = nameEpFilter

                        episodeData["priority"] = f"{mode}.{str(int(nameEpFilter or '0')):>05}"

                        epData.append(episodeData)

            for episodeData in sorted(epData, key=lambda data: data["priority"]):
                # print(episodeData)
                if episodeData["mode"] <= 3:
                    newEp = EpisodeWidget(
                        width=self.epWidgetWidth,
                        height=self.epWidgetHeight,
                        episodeNumber=episodeData["number"],
                        title=episodeData["title"],
                        name=episodeData["name"],
                        colour=episodeData["colour"],
                        view=episodeData["view"],
                        aniTitle=data[4],
                        thumbnailSource=data[1],
                        aniTitleGood=data[0],
                        aniUrl=aniUrl,
                        maxEpNum=len(epData)
                    )

                    episodeGridLayout.add_widget(newEp)

            episodeGridLayout = self.ids.EpisodeGridLayout
            episodeGridLayout.y = 0

            scrollSearchGrid = self.ids.ScrollSearchGrid
            scrollSearchGrid.scroll_to(self.ids.Thumbnail)

            threading.Thread(target=self.updateImageTextures, args=([(self.ids.Thumbnail.__self__, data[1])],),
                             daemon=True).start()

        self.aniUrl = aniUrl
        self.extraNames = extraNames
        loadThread = threading.Thread(target=loadAniData, args=(aniUrl,), daemon=True)
        loadThread.start()

    def refreshEpisodeColours(self, *args):
        storedData = JsonStore("data.json")
        recentlyWatchedData = GetDataStore(storedData, "RecentlyWatched", default={})
        aniRecentData = recentlyWatchedData[self.aniRawName] if self.aniRawName in recentlyWatchedData else {}
        
        episodeGridLayout = self.ids.EpisodeGridLayout

        aniData = GetDataStore(storedData, "AniData", default={})
        maxEps = self.aniRawName in aniData and aniData[self.aniRawName][0] or 0
        self.ids.EpisodeCounter.text = f"{len(aniRecentData.keys())}/{maxEps}"

        for widget in episodeGridLayout.children:
            widget.isHighlighted = widget.episodeNumber in aniRecentData
        
    def EpisodeButtonPressed(self, instance):
        self.parent.manager.transition.direction = 'down'
        self.parent.manager.current = "VideoPlayer"

        self.videoWindow.initiate(instance)
        
    def EpisodeButtonPressedLong(self, instance):
        storedData = JsonStore("data.json")
        recentlyWatchedData = GetDataStore(storedData, "RecentlyWatched", default={})

        if self.aniRawName not in recentlyWatchedData:
            recentlyWatchedData[self.aniRawName] = {}

        if instance.episodeNumber in recentlyWatchedData[self.aniRawName]:
            del recentlyWatchedData[self.aniRawName][str(instance.episodeNumber)]
        
        else:
            recentlyWatchedData[self.aniRawName][str(instance.episodeNumber)] = [
                time(),
                instance.aniTitleGood,
                instance.episodeNumber,
                instance.thumbnailSource,
                instance.view,
                instance.aniUrl, 
                instance.maxEpNum,
                True
            ]

        storedData["RecentlyWatched"] = recentlyWatchedData
        self.refreshEpisodeColours()
        
    
class VideoWindow(Widget):
    title = StringProperty("")
    name = StringProperty("")
    positionDurationString = StringProperty("0")
    volumeString = StringProperty("0")

    touchTime = time()
    touchDuration = 5
    pauseTime = time()
    pauseTimeOutRefresh = 50

    play = True
    guiState = 0

    sliderTouched = False
    sliderAdjustCode = True

    normalisedDuration = NumericProperty(0)

    finalUrls = []

    rowClicked = False

    videoInfoHeight = NumericProperty(0)
    videoInfoWidth = NumericProperty(0)

    lackingEnabled = False
    isLacking = False

    pinned = False
    appTitle = ""
    recentBypass = False

    infoWindow = None
    viewLink = ""

    chromePath = ""

    seekTime = 0
    seekingPause = False
    seekingStartTime = 0
    seekingLastUpdate = 0
    seekingCanRegister = False
    seekingCustomTime = None

    videoCounting = 0
    videoValidity = []

    dRPC = None

    def initiate(self, episodeInstance, recentBypass=False):
        def loadVideo(videoId, mainWidget, videoWidget, episodeInstance):
            def episodeError(instance):
                instance.mainWidget.Android_back_click(None, 27)

            finalUrls = webscraper.extractVideoFiles(episodeInstance.view, mainWidget.chromePath)
            finalUrls = sorted(finalUrls, key=lambda data: int(data[1].split("x")[0]))

            privateMode = True
            storedData = JsonStore("data.json")
            if "Settings" in storedData and "DiscordRPCMode" in storedData["Settings"]:
                settings = storedData["Settings"]
                privateMode = settings["DiscordRPCMode"] != "public"
            else:
                data = storedData["Settings"]
                data["DiscordRPCMode"] = "private"
                storedData["Settings"] = data

            if privateMode:
                self.dRPC.update(f"Watching...", None, int(time()))
            else:
                self.dRPC.update(f"Watching {episodeInstance.aniTitleGood}", f"Episode {episodeInstance.episodeNumber}", int(time()))

            if not mainWidget.videoValidity[videoId]:
                return

            if not len(finalUrls):
                button = Button(
                    text='Failed to get Video Data, Please Check your Connection',
                    # size_hint=(0.6, 1),
                )

                def setButtonTextSize(instance, size):
                    instance.text_size[0] = size[0] * 0.8

                button.bind(size=setButtonTextSize)
                popup = Popup(title='Failed to Load Episode',
                              content=button,
                              size_hint=(0.8, 0.8),
                              auto_dismiss=False)
                popup.mainWidget = mainWidget
                popup.bind(on_dismiss=episodeError)
                button.bind(on_release=popup.dismiss)
                popup.open()

                return

            # Exiting before data is received
            if mainWidget.title != "":
                mainWidget.finalUrls = finalUrls

                if len(mainWidget.finalUrls) > 0:
                    videoWidget.source = [data for data in mainWidget.finalUrls if data[0] != "NA"][-1][0]

                    if not self.isLacking:
                        videoWidget.state = "play"

                    for data in finalUrls:
                        if data[0] == "NA":
                            newWidget = VideoInfo(text=f"{data[1]} - NA", size=(self.videoInfoWidth, self.videoInfoHeight), sourceLink=data[0])
                        else:
                            newWidget = VideoInfo(text=data[1], size=(self.videoInfoWidth, self.videoInfoHeight), sourceLink=data[0])
                        newWidget.bind(on_press=self.VideoInfoButtonClicked)
                        self.ids.RowsGridLayout.add_widget(newWidget)

                    while videoWidget.duration == -1 or videoWidget.duration == 1:
                        sleep(0.1)

                    storedData = JsonStore("data.json")

                    resumeData = GetDataStore(storedData, "ResumeData", default={})
                    timePos = resumeData.get(episodeInstance.title, None)

                    recentlyWatchedData = GetDataStore(storedData, "RecentlyWatched", default={})

                    aniTitle = episodeInstance.aniTitle
                    if aniTitle not in recentlyWatchedData:
                        recentlyWatchedData[aniTitle] = {}

                    recentlyWatchedData[aniTitle][str(episodeInstance.episodeNumber)] = [
                        time(),
                        episodeInstance.aniTitleGood,
                        episodeInstance.episodeNumber,
                        episodeInstance.thumbnailSource,
                        episodeInstance.view,
                        episodeInstance.aniUrl, 
                        episodeInstance.maxEpNum,
                        False
                    ]
                    storedData["RecentlyWatched"] = recentlyWatchedData

                    if timePos and not self.isLacking:
                        mainWidget.TogglePlayPause(bypass=True, forceRefresh=True, overridePlayPosition=max(timePos-5, 0))

                    # mainWidget.touchTime = time() + mainWidget.touchDuration
                else:
                    button = Button(
                        text='Please Re-Search this Anime, If Problems Still Occur, Please Contact Me on the ABOUT Section',
                        #size_hint=(0.6, 1),
                    )

                    def setButtonTextSize(instance, size):
                        instance.text_size[0] = size[0]*0.8

                    button.bind(size=setButtonTextSize)
                    popup = Popup(title='Failed to Load Episode',
                                  content=button,
                                  size_hint=(0.8, 0.8),
                                  auto_dismiss=False)
                    popup.mainWidget = mainWidget
                    popup.bind(on_dismiss=episodeError)
                    button.bind(on_release=popup.dismiss)
                    popup.open()

        video = self.ids.VideoWidget
        self.recentBypass = recentBypass
        self.viewLink = episodeInstance.aniUrl
        # video.state = "play"

        self.ids.DurationSlider.bind(value=self.SliderDurationValueChanged)
        self.ids.VolumeSlider.bind(value=self.VolumeDurationValueChanged)

        self.ids.RowsGridLayout.clear_widgets()

        self.title = episodeInstance.title
        self.name = episodeInstance.name

        storedData = JsonStore("data.json")
        if "Settings" not in storedData:
            storedData["Settings"] = {}

        data = GetDataStore(storedData, "Settings", default={})

        if "LackingEnabled" not in data:
            storedData["Settings"] = {"LackingEnabled": "false"}
            data = GetDataStore(storedData, "Settings", default={})

        if data.get("LackingEnabled") == "true":
            self.lackingEnabled = True

        Window.bind(on_keyboard=self.Android_back_click)

        self.videoValidity.append(True)
        threading.Thread(target=loadVideo, args=(self.videoCounting, self, video, episodeInstance,), daemon=True).start()
        self.videoCounting += 1

    def Android_back_click(self, window, key, *largs):
        if self.parent.manager.current == "VideoPlayer":
            # Escape
            if key == 27:
                self.videoValidity[self.videoCounting - 1] = False

                Window.fullscreen = False
                self.BackButtonClicked(bypass=True)

                video = self.ids.VideoWidget
                video.state = "stop"
                video.source = ""
                video.unload()

                self.parent.manager.transition.direction = 'up'
                self.parent.manager.current = "AniInfoWindow"

                self.dRPC.update(f"Idle", None, None)

                if self.recentBypass:
                    self.infoWindow.generateAniData(self.viewLink, "")

                self.viewLink = ""

                self.title = ""
                self.name = ""
                self.positionDurationString = "0"
                self.volumeString = "0"

                self.touchTime = time()
                self.pauseTime = time()

                self.play = True
                self.guiState = 0

                self.sliderTouched = False
                self.sliderAdjustCode = True

                self.normalisedDuration = 0

                self.finalUrls = []

                self.rowClicked = False
                self.recentBypass = False

                if platform == "win":
                    self.pinned = False
                    unregister_topmost(Window, self.appTitle)

                return True

            # N
            elif key == 110:
                if self.lackingEnabled:
                    self.isLacking = not self.isLacking

                    if self.isLacking:
                        self.play = False
                        self.TogglePlayPause(bypass=True, noReload=True)

            # Space
            elif key == 32 and not self.isLacking:
                self.TogglePlayPause(toggleBypass=True)

            # Up
            elif key == 273:
                origValue = self.ids.VolumeSlider.value
                self.ids.VolumeSlider.value = max(0, min(100, origValue + 5))

            # Down
            elif key == 274:
                origValue = self.ids.VolumeSlider.value
                self.ids.VolumeSlider.value = max(0, min(100, origValue - 5))

            # Left
            elif key == 276:
                self.FastBackward(bypass=True)

            # Right
            elif key == 275:
                self.FastForward(bypass=True)

    def BackButtonClicked(self, *args, bypass=False):
        if self.ids.BackButton.opacity or bypass:
            Title = self.title
            PlayingPosition = self.ids.VideoWidget.position
            Duration = self.ids.VideoWidget.duration

            storedData = JsonStore("data.json")

            if PlayingPosition != Duration:
                data = GetDataStore(storedData, "ResumeData", default={})
                data[Title] = PlayingPosition

                storedData["ResumeData"] = data
            else:
                data = GetDataStore(storedData, "ResumeData", default={})

                if Title in data:
                    del data[Title]

                storedData["ResumeData"] = data

            if not bypass:
                self.Android_back_click(None, 27)
        else:
            self.touchButtonTouched()

    def PinToggle(self, reloadImage=False):
        if not reloadImage:
            if self.ids.PinButton.opacity and platform == "win":
                self.pinned = not self.pinned

                self.ids.PinImage.source = self.pinned and "resources/pinC.png" or "resources/pin.png"

                if self.pinned:
                    register_topmost(Window, self.appTitle)
                else:
                    unregister_topmost(Window, self.appTitle)

                self.touchTime = time() + 5
            else:
                self.touchButtonTouched()

        if reloadImage:
            self.ids.PinImage.source = self.pinned and "resources/pinC.png" or "resources/pin.png"

    def FullScreenToggle(self, *args):
        fullScreenImage = self.ids.FullScreenImage
        imagePath = fullScreenImage.source

        if self.ids.FullScreenButton.opacity:
            if "On" in imagePath:
                Window.fullscreen = "auto"
                fullScreenImage.source = "resources/FullScreenOff.png"
            elif "Off" in imagePath:
                Window.fullscreen = False
                fullScreenImage.source = "resources/FullScreenOn.png"

            self.touchTime = time() + 5
        else:
            self.touchButtonTouched()

    def DownloadToggle(self, *args):
        if self.ids.DownloadButton.opacity:
            webbrowser.open(self.ids.VideoWidget.source)
            self.touchTime = time() + 5
        else:
            self.touchButtonTouched()

    def FastForward(self, bypass=False, *args):
        if self.ids.FastForwardButton.opacity or bypass:

            #position = min(max(video.position + 5, 0), video.duration)
            #video.seek(position/video.duration, precise=True)

            video = self.ids.VideoWidget
            video.state = "pause"

            self.seekTime += 5
            self.seekingCustomTime = min(max(video.position + self.seekTime, 0), video.duration)
            self.seekingLastUpdate = time()
            self.touchTime = time() + 5
            self.seekingCanRegister = True

        else:
            self.touchButtonTouched()

    def FastBackward(self, bypass=False, *args):
        if self.ids.FastBackwardButton.opacity or bypass:
            #video = self.ids.VideoWidget

            #position = min(max(video.position - 5, 0), video.duration)
            #video.seek(position/video.duration, precise=True)

            video = self.ids.VideoWidget
            video.state = "pause"

            self.seekTime -= 5
            self.seekingCustomTime = min(max(video.position + self.seekTime, 0), video.duration)
            self.seekingLastUpdate = time()
            self.touchTime = time() + 5
            self.seekingCanRegister = True

        else:
            self.touchButtonTouched()

    def VideoSeekTimeUpdater(self, *args):
        if self.parent.manager.current == "VideoPlayer" and self.seekTime and not self.seekingPause and self.seekingCanRegister:
            video = self.ids.VideoWidget

            if video.duration == -1:
                return

            if time() > self.seekingLastUpdate + 1:
                self.seekingCanRegister = False

                video = self.ids.VideoWidget
                video.state = "play"

                position = min(max(video.position + self.seekTime, 0), video.duration)
                video.seek(position / video.duration, precise=True)
                self.seekTime = 0
                self.seekingCustomTime = None

    def refreshPositionSlider(self, *args):
        def convertTimeToDuration(time):
            return f"{time // 3600:0>2}:{time // 60 - (time // 3600) * 60:0>2}:{time % 60:0>2}" if time >= 3600 else f"{time // 60:0>2}:{time % 60:0>2}"

        width, height = Window.size

        durationSlider = self.ids.DurationSlider
        positionSliderInfo = self.ids.PositionSliderInfo

        if self.sliderTouched:
            positionSliderInfo.text = convertTimeToDuration(int(durationSlider.value))
            positionSliderInfo.x = durationSlider.value_pos[0] - positionSliderInfo.width/2
            positionSliderInfo.y = durationSlider.value_pos[1] + durationSlider.padding

        else:
            positionSliderInfo.pos = (width*2, height*2)

    def refreshCurrentQuality(self, *args):
        video = self.ids.VideoWidget
        source = video.source
        qualityGrid = self.ids.RowsGridLayout

        if source not in ["", "NA"]:
            for quality in qualityGrid.children:
                qSource: str = quality.sourceLink
                qText: str = quality.text
                if qSource == source:
                    if not qText.startswith("[b]") and not qText.endswith("[/b]"):
                        quality.text = f"[b]{qText}[/b]"
                else:
                    quality.text = quality.text.replace("[b]", "").replace("[/b]", "")

    def refresh(self, *args):
        def convertTimeToDuration(time):
            return f"{time // 3600:0>2}:{time // 60 - (time // 3600) * 60:0>2}:{time % 60:0>2}" if time >= 3600 else f"{time // 60:0>2}:{time % 60:0>2}"

        width, height = Window.size

        self.PinToggle(reloadImage=True)

        if self.lackingEnabled:
            self.ids.Lacking.pos = (0, 0) if self.isLacking else (width*2, height*2)

            if self.isLacking:
                self.ids.VideoWidget.state = "pause"

        self.videoInfoWidth = width * 0.2
        self.videoInfoHeight = height/30 * 2

        children = self.ids.RowsGridLayout.children
        for child in children:
            child.size = (self.videoInfoWidth, self.videoInfoHeight)
            child.font_size = height/30

            #print("Setting")

        video = self.ids.VideoWidget

        title = self.ids.Title
        title.text_size = title.size

        position = video.position >= 0 and ceil(video.position) or 0
        if self.seekingCustomTime:
            position = ceil(self.seekingCustomTime)

        volumeSlider = self.ids.VolumeSlider
        volumeSlider.y = volumeSlider.padding/2 + height*0.01 if volumeSlider.opacity else -50 - volumeSlider.padding - height*0.01

        volumeSlider.cursor_size = height*0.08 * 0.75, height*0.08 * 0.75
        volumeSlider.padding = (height*0.08 * 0.75) / 4
        #durationSlider.value_track_width = height/(36*1.5)
        volumeSlider.size = width*0.55, height*0.08*0.75
        volumeSlider.background_width = volumeSlider.size[1]

        self.positionDurationString = convertTimeToDuration(position) + " / " + convertTimeToDuration(video.duration >= 0 and ceil(video.duration) or 0)
        positionDurationText = self.ids.PositionDurationText
        positionDurationText.text_size = positionDurationText.size
        positionDurationText.pos = height*0.02, height*0.02

        self.volumeString = f"{int(volumeSlider.value)}%"
        volumeText = self.ids.VolumeText
        volumeText.text_size = volumeText.size
        volumeText.pos = width * 0.325 - (4 * height * 0.05 * 0.55) - 2*(height*(0.08*0.75+0.02)) - height*0.02, height * 0.01 + (height*0.08 * 0.75) / 4# - volumeText.size[1]/2

        durationSlider = self.ids.DurationSlider
        durationSlider.max = ceil(video.duration)
        durationSlider.y = height*0.08*0.75 + height*0.01 + durationSlider.padding if durationSlider.opacity else -50 - height/36 - (height*0.1 + height*0.03)
        
        durationSlider.cursor_size = height*0.08 * 0.75, height*0.08 * 0.75
        durationSlider.padding = (height*0.08 * 0.75) / 4
        #durationSlider.value_track_width = height/(36*1.5)
        durationSlider.size = width*0.97, height*0.08*0.75
        durationSlider.background_width = durationSlider.size[1]

        #durationSlider.cursor_image = "circle.png" if self.sliderTouched else "blank.png"
        self.normalisedDuration = video.position / video.duration

        if self.play:
            self.pauseTime = time()

        if not self.sliderTouched:
            self.sliderAdjustCode = True
            durationSlider.value = ceil(position)

        self.RowClicked(bypass=True)
        self.TogglePlayPause(bypass=True)

        guis = [
            title,
            self.ids.PlayPauseButton,
            self.ids.BackButton,
            self.ids.BackgroundButton,
            positionDurationText,
            volumeText,
            durationSlider,
            volumeSlider,
            self.ids.FullScreenButton,
            self.ids.DownloadButton,
            self.ids.RowsButton,
            self.ids.RowsGridLayout,
            self.ids.FastForwardButton,
            self.ids.FastBackwardButton
        ]

        if platform == "win":
            guis.append(self.ids.PinButton)

        state = int(self.touchTime > time())
        #durationSlider.disabled = state ^ 1
        self.guiState = state

        for gui in guis:
            gui.opacity = state

    def VideoInfoButtonClicked(self, instance, value=None):
        if instance.sourceLink == "NA" or self.ids.VideoWidget.source == instance.sourceLink:
            return

        self.TogglePlayPause(bypass=True, forceRefresh=True, overrideSource=instance.sourceLink)

    def touchButtonTouched(self):
        title = self.ids.Title

        self.touchTime = time() + (title.opacity ^ 1) * 5

    def Slider_TouchUpDown(self, isDown):
        self.sliderTouched = isDown

    def SliderDurationValueChanged(self, instance, value):
        video = self.ids.VideoWidget
        durationSlider = self.ids.DurationSlider

        if not self.sliderAdjustCode and video.loaded:
            video.state = "pause"
            self.TogglePlayPause(bypass=True)
            video.seek(durationSlider.value_normalized, precise=True)
            video.state = "play"
            self.TogglePlayPause(bypass=True)

            self.touchTime = time() + 5

        self.sliderAdjustCode = False

    def VolumeDurationValueChanged(self, instance, value):
        video = self.ids.VideoWidget
        video.volume = instance.value_normalized
        self.touchTime = time() + 5

    def RowClicked(self, bypass=False):
        if not bypass and not self.ids.RowsButton.opacity:
            self.touchButtonTouched()
            return

        if not bypass:
            self.rowClicked = not self.rowClicked

        width, height = Window.size

        grid = self.ids.RowsGridLayout
        grid.x = self.rowClicked and width*0.8 - height*0.01 or width
        grid.opacity = 1

    def TogglePlayPause(self, bypass=False, toggleBypass=False, forceRefresh=False, overrideSource=None, overridePlayPosition=None, noReload=False):
        if not self.guiState and not bypass and not toggleBypass:
            self.touchButtonTouched()

        else:
            video = self.ids.VideoWidget
            oldPlay = self.play

            if not bypass or toggleBypass:
                self.play = not self.play
            else:
                self.play = video.state == "play"

            self.ids.PlayPauseButtonImage.source = not self.play and "resources/PlayButtonW.png" or "resources/PauseButtonW.png"

            video.state = self.play and "play" or "pause"

            if ((self.play and not oldPlay and time() > self.pauseTime + self.pauseTimeOutRefresh) or forceRefresh) and not noReload:
                self.pauseTime = time()

                logging.info(f"Reloader: Reloading Source")

                durationSlider = self.ids.DurationSlider
                currentNormalValue = durationSlider.value_normalized
                if overridePlayPosition is not None:
                    currentNormalValue = overridePlayPosition / video.duration

                oldSource = overrideSource or video.source

                video.state = "pause"
                video.source = ""
                video.source = oldSource
                video.state = "play"

                def seekNormalTime(seekVal):
                    sleep(1)
                    logging.info(f"Reloader: Seeking to {seekVal}")

                    video.seek(seekVal, precise=True)
                    self.sliderTouched = False

                threading.Thread(target=seekNormalTime, args=(currentNormalValue,), daemon=True).start()


class AniApp(App):
    videoWindow = None

    def build(self):
        chromePath = ChromeDriverManager().install()

        self.title = 'PhoenixAnistream'
        self.icon = r".\resources\PhoenixAniStream.ico"
        Window.set_title(self.title)

        DiscordRPC = DiscordRichPresenceHandler()
        DiscordRPC.update("Idle", None, None)

        windowManager = WindowManager()
        homeWindow = windowManager.ids.HomeWindow
        infoWindow = windowManager.ids.InfoWindow
        videoWindow = windowManager.ids.VideoWindow

        homeWindow.dRPC = DiscordRPC
        infoWindow.dRPC = DiscordRPC
        videoWindow.dRPC = DiscordRPC

        videoWindow.appTitle = self.title
        videoWindow.infoWindow = infoWindow
        videoWindow.chromePath = chromePath
        self.videoWindow = videoWindow
        homeWindow.infoWindowWidget = infoWindow
        infoWindow.videoWindow = videoWindow
        homeWindow.videoWindow = videoWindow
        # homeWindow = HomeWindow()

        Clock.schedule_once(homeWindow.updateLatestAniData, 0)
        Clock.schedule_once(homeWindow.setWidget, -1)

        Clock.schedule_interval(homeWindow.updateVars, 1 / 30)
        Clock.schedule_interval(homeWindow.updateAniWidgets, 1 / 60)
        Clock.schedule_interval(homeWindow.RefreshRecentlyWatched, 1)
        Clock.schedule_interval(homeWindow.RefreshBookmarkedAni, 1)

        Clock.schedule_interval(infoWindow.refreshDescription, 1 / 60)
        Clock.schedule_interval(infoWindow.refreshEpisodeColours, 1 / 2)
        #Clock.schedule_interval(infoWindow.updateVars, 1/2)
        # Clock.schedule_interval(homeWindow.pollSearchInput, 1/10)

        Clock.schedule_interval(videoWindow.refresh, 1 / 10)
        Clock.schedule_interval(videoWindow.refreshPositionSlider, 1 / 60)
        Clock.schedule_interval(videoWindow.VideoSeekTimeUpdater, 1/20)
        Clock.schedule_interval(videoWindow.refreshCurrentQuality, 1/10)

        windowManager.transition = SlideTransition()
        # windowManager.current = "MainWindow"
        # self.manager.transition.direction = "left"

        return windowManager


def ProgramClosed(app):
    VideoWindow = app.videoWindow
    Title = VideoWindow.title
    PlayingPosition = VideoWindow.ids.VideoWidget.position
    Duration = VideoWindow.ids.VideoWidget.duration

    storedData = JsonStore("data.json")

    if PlayingPosition != Duration:
        data = GetDataStore(storedData, "ResumeData", default={})
        data[Title] = PlayingPosition

        storedData["ResumeData"] = data
    else:
        data = GetDataStore(storedData, "ResumeData", default={})

        if Title in data:
            del data[Title]

        storedData["ResumeData"] = data


if __name__ == '__main__':
    try:
        mkdir("cache")
    except:
        pass

    storedData = JsonStore("data.json")

    if "ScreenSize" in storedData:
        Window.size = storedData["ScreenSize"]["size"]
    else:
        storedData["ScreenSize"] = {"size": (1280 / 2, 720 / 2)}
        Window.size = (1280 / 2, 720 / 2)

    app = AniApp()

    atexit.register(ProgramClosed, app)
    app.run()
