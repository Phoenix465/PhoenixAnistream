import atexit
import logging
import queue
import threading
import webbrowser

import kivy
from kivy.storage.jsonstore import JsonStore
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

kivy.require('2.0.0')  # replace with your current kivy version !

from kivy.core.window import Window
#Window.size = (1280 / 2, 720 / 2)

from kivy.config import Config
Config.set('kivy', 'exit_on_escape', '0')
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import NumericProperty, BooleanProperty, StringProperty
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.clock import mainthread
import os.path as path
from os import mkdir

# from kivy.loader import Loader
# Loader.loading_image = "loading.gif"

from math import ceil
import requests
from concurrent.futures import ThreadPoolExecutor

import webscraper
import sys
from time import time, sleep

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

    searchQueue = queue.LifoQueue()
    latestSearchThread = None

    infoWindowWidget = None

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

        gridLayout = self.ids.AniGridLayout if searchBox.opacity == 0 else self.ids.SearchGridLayout
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
                rows += 1

                # print(textS, rowsLengths)

                if rows > maxRows:
                    maxRows = rows

                    # print(maxRows, textS, rowsLengths)
            # print()
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
            request = requests.get(url)
            if request.ok:
                content = request.content
                file = open(filePath, "wb")
                file.write(content)
                file.close()

                self.loadImageTexture(image, filePath)
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

        self.remove_widget(self.ids.PlaceHolder2)
        self.remove_widget(self.ScrollSearchGrid)

        searchBox = self.ids.TextInputSearchBox
        searchBox.bind(text=self.searchInputChanged)

        # Fixes weird clipping issue on name label when using screen manager...
        self.remove_widget(self.ScrollAniGrid)
        self.add_widget(self.ScrollSearchGrid)
        self.add_widget(self.ScrollAniGrid)
        self.remove_widget(self.ScrollSearchGrid)

        # self.SearchButtonToggle()
        # self.SearchButtonToggle()

    def searchData(self, searchQuery):
        @mainthread
        def addWidgets(searchData, genreData):
            threadData = []

            for i, data in enumerate(searchData):
                thumbnailUrl = data["thumbnail"]

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
                    fontSize=self.fontSize,
                    data=data)

                gridLayout.add_widget(widget)

                threadData.append((widget.ids.Thumbnail.__self__, thumbnailUrl))

            self.updateAniWidgets(0, override=True)

            updateThread = threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True)
            updateThread.start()
            threading.Thread(target=self.runSearchQueue, daemon=True).start()

        searchData = webscraper.SearchDataAnimeDaoTo(searchQuery)
        genreData = webscraper.GetAniGenres(searchData)
        gridLayout = self.ids.SearchGridLayout
        gridLayout.clear_widgets()

        addWidgets(searchData, genreData)

    def searchInputChanged(self, *args, reload=False):
        searchBox = self.ids.TextInputSearchBox

        if searchBox.opacity == 1:
            searchQuery = searchBox.text

            if len(searchQuery) >= 3:
                if self.ScrollAniGrid.parent == self:
                    self.remove_widget(self.ScrollAniGrid)

                if self.ScrollSearchGrid.parent != self:
                    self.add_widget(self.ScrollSearchGrid)

                if not reload:
                    with self.searchQueue.mutex:
                        self.searchQueue.queue.clear()

                    thread = threading.Thread(target=self.searchData, args=(searchQuery,), daemon=True)
                    self.searchQueue.put(thread)

                    if self.searchQueue.qsize() == 1 and not (
                            self.latestSearchThread and self.latestSearchThread.is_alive):
                        self.runSearchQueue()

            else:
                if self.ScrollAniGrid.parent != self:
                    self.add_widget(self.ScrollAniGrid)

                if self.ScrollSearchGrid.parent == self:
                    self.remove_widget(self.ScrollSearchGrid)

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

    def SearchButtonToggle(self, skip=False):
        if not skip:
            self.searchToggle = not self.searchToggle

        duration = 0 if skip else 0.2

        titleNameWidget = self.ids.Title
        searchBox = self.ids.TextInputSearchBox
        searchButton = self.ids.SearchButton
        backButton = self.ids.BackButton

        if not skip:
            if self.searchToggle:
                searchBox.text = ""
            else:
                if self.ScrollAniGrid.parent != self:
                    self.add_widget(self.ScrollAniGrid)

                if self.ScrollSearchGrid.parent == self:
                    self.remove_widget(self.ScrollSearchGrid)

        size = Window.size

        if self.searchToggle:
            searchButton.disabled = True
            searchButton.opacity = 0

            backButton.disabled = False
            backButton.opacity = 1

            titleAnim = Animation(x=-size[0] / 2 - (size[1] * 0.1 * 0.4) * len(titleNameWidget.text) / 2 * 0.6,
                                  duration=duration)
            titleAnim.start(titleNameWidget)

            searchBoxAnim = Animation(x=size[0] * 0.075, width=size[0] * 0.8, opacity=1, duration=duration)
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

            searchBoxAnim = Animation(x=size[0] * 0.9, width=0, opacity=0, duration=duration)
            searchBoxAnim.start(searchBox)
            searchBox.readonly = True

    def AniSearchButtonPressed(self, instance):
        if instance.data:
            self.parent.manager.transition.direction = 'down'
            self.parent.manager.current = "AniInfoWindow"

            self.infoWindowWidget.generateAniData(instance.data["ani"])


class InfoWindow(Widget):
    aniName = StringProperty("")

    epWidgetWidth = NumericProperty(Window.size[1] * 0.1)
    epWidgetHeight = NumericProperty(Window.size[1] * 0.1)

    gridCols = NumericProperty(5)
    spacingX = NumericProperty(20)

    placeholderExists = True

    videoWindow = None

    def BackArrowPressed(self):
        self.parent.manager.transition.direction = 'up'
        self.parent.manager.current = "MainWindow"

        self.ids.description.textDescription = ""
        self.ids.EpisodeGridLayout.clear_widgets()
        self.aniName = ""
        self.ids.Thumbnail.source = "loading.gif"

    def updateImageTexture(self, data):
        image, url = data
        fileName = url.split("/")[-1]
        filePath = path.join("cache", fileName)

        if not path.isfile(filePath):
            request = requests.get(url)
            if request.ok:
                content = request.content
                file = open(filePath, "wb")
                file.write(content)
                file.close()

                self.loadImageTexture(image, filePath)
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

        self.updateVars()

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

        self.ids.RelLayout.height = episodeGridLayout.minimum_height + episodeInput.height + descriptionId.height + self.ids.Thumbnail.height + (
                    0.05 * 3 * height)
        episodeGridLayout.y = 0

    def searchClicked(self):
        episodeGridLayout = self.ids.EpisodeGridLayout
        scrollSearchGrid = self.ids.ScrollSearchGrid
        episodeInput = self.ids.EpisodeInput

        for widget in episodeGridLayout.children:
            if int(widget.ids.ButtonWidget.text or '-1') == int(episodeInput.ids.EpisodeInputInput.text or '-2'):
                scrollSearchGrid.scroll_to(widget)

    def generateAniData(self, aniUrl):
        def loadAniData(url):
            data = webscraper.GetAniData(aniUrl)

            self.aniName = data[0]

            descriptionId = self.ids.description
            descriptionId.textDescription = data[2]
            self.refreshDescription()

            episodeGridLayout = self.ids.EpisodeGridLayout

            if self.placeholderExists:
                episodePlaceHolder = self.ids.EpisodePlaceHolder
                episodeGridLayout.remove_widget(episodePlaceHolder)
                self.placeholderExists = False

            titleAlready = []

            movies = 0
            special = 0
            extra = 0

            epData = []
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

            episodeGridLayout.clear_widgets()

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
                    )

                    episodeGridLayout.add_widget(newEp)

            episodeGridLayout = self.ids.EpisodeGridLayout
            episodeGridLayout.y = 0

            scrollSearchGrid = self.ids.ScrollSearchGrid
            scrollSearchGrid.scroll_to(self.ids.Thumbnail)

            threading.Thread(target=self.updateImageTextures, args=([(self.ids.Thumbnail.__self__, data[1])],),
                             daemon=True).start()

        loadThread = threading.Thread(target=loadAniData, args=(aniUrl,), daemon=True)
        loadThread.start()

    def EpisodeButtonPressed(self, instance):
        self.parent.manager.transition.direction = 'down'
        self.parent.manager.current = "VideoPlayer"

        self.videoWindow.initiate(instance)


class VideoWindow(Widget):
    title = StringProperty("")
    name = StringProperty("")
    positionDurationString = StringProperty("0")
    volumeString = StringProperty("0")

    touchTime = time()
    touchDuration = 5
    pauseTime = time()
    pauseTimeOutRefresh = 300

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

    def initiate(self, episodeInstance):
        def loadVideo(mainWidget, videoWidget, episodeInstance):
            def episodeError(instance):
                instance.mainWidget.Android_back_click(None, 27)

            finalUrls = webscraper.extractVideoFiles(episodeInstance.view)

            # Exiting before data is received
            if mainWidget.title != "":
                mainWidget.finalUrls = finalUrls

                if len(mainWidget.finalUrls) > 0:
                    videoWidget.source = mainWidget.finalUrls[-1][0]

                    if not self.isLacking:
                        videoWidget.state = "play"

                    for data in finalUrls:
                        newWidget = VideoInfo(text=data[1], size=(self.videoInfoWidth, self.videoInfoHeight), sourceLink=data[0])
                        newWidget.bind(on_press=self.VideoInfoButtonClicked)
                        self.ids.RowsGridLayout.add_widget(newWidget)

                    while videoWidget.duration == -1 or videoWidget.duration == 1:
                        sleep(0.1)

                    storedData = JsonStore("data.json")

                    data = GetDataStore(storedData, "ResumeData", default={})
                    timePos = data.get(episodeInstance.title, None)

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

        threading.Thread(target=loadVideo, args=(self, video, episodeInstance,), daemon=True).start()

    def Android_back_click(self, window, key, *largs):
        if self.parent.manager.current == "VideoPlayer":
            if key == 27:
                self.BackButtonClicked(bypass=True)

                video = self.ids.VideoWidget
                video.state = "stop"
                video.source = ""
                video.unload()

                self.parent.manager.transition.direction = 'up'
                self.parent.manager.current = "AniInfoWindow"

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

                return True

            elif key == 110:
                if self.lackingEnabled:
                    self.isLacking = not self.isLacking

                    if self.isLacking:
                        self.play = False
                        self.TogglePlayPause(bypass=True, noReload=True)

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

    def refresh(self, *args):
        def convertTimeToDuration(time):
            return f"{time // 3600:0>2}:{time // 60 - (time // 3600) * 60:0>2}:{time % 60:0>2}" if time >= 3600 else f"{time // 60:0>2}:{time % 60:0>2}"

        width, height = Window.size

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

        self.positionDurationString = convertTimeToDuration(video.position >= 0 and ceil(video.position) or 0) + " / " + convertTimeToDuration(video.duration >= 0 and ceil(video.duration) or 0)
        positionDurationText = self.ids.PositionDurationText
        positionDurationText.text_size = positionDurationText.size
        positionDurationText.pos = 0, 0

        volumeSlider = self.ids.VolumeSlider
        volumeSlider.y = height/36 if volumeSlider.opacity else -50 - height/36

        self.volumeString = f"{int(volumeSlider.value)}%"
        volumeText = self.ids.VolumeText
        volumeText.text_size = volumeText.size
        volumeText.pos = width * 0.5 - (4 * height * 0.05 * 0.55), height * 0.01

        durationSlider = self.ids.DurationSlider
        durationSlider.max = ceil(video.duration)
        durationSlider.y = height*0.1 if durationSlider.opacity else -50 - height/36
        #durationSlider.cursor_image = "circle.png" if self.sliderTouched else "blank.png"
        self.normalisedDuration = video.position / video.duration

        if self.play:
            self.pauseTime = time()

        if not self.sliderTouched:
            self.sliderAdjustCode = True
            durationSlider.value = ceil(video.position)

        self.RowClicked(bypass=True)
        self.TogglePlayPause(bypass=True)

        guis = [title, self.ids.PlayPauseButton, self.ids.BackButton, self.ids.BackgroundButton, positionDurationText, volumeText, durationSlider, volumeSlider]

        state = int(self.touchTime > time())
        #durationSlider.disabled = state ^ 1
        self.guiState = state

        for gui in guis:
            gui.opacity = state

    def VideoInfoButtonClicked(self, instance, value=None):
        self.TogglePlayPause(bypass=True, forceRefresh=True, overrideSource=instance.sourceLink)

    def touchButtonTouched(self):
        title = self.ids.Title

        self.touchTime = time() + (title.opacity ^ 1) * 5

    def Slider_TouchUpDown(self, isDown):
        self.sliderTouched = isDown

    def SliderDurationValueChanged(self, instance, value):
        video = self.ids.VideoWidget
        durationSlider = self.ids.DurationSlider

        if not self.sliderAdjustCode:
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
        if not bypass:
            self.rowClicked = not self.rowClicked

        width, height = Window.size

        grid = self.ids.RowsGridLayout
        grid.x = self.rowClicked and width*0.8 or width

    def TogglePlayPause(self, bypass=False, forceRefresh=False, overrideSource=None, overridePlayPosition=None, noReload=False):
        if not self.guiState and not bypass:
            self.touchButtonTouched()

        else:
            video = self.ids.VideoWidget
            oldPlay = self.play

            if not bypass:
                self.play = not self.play
            else:
                self.play = video.state == "play"

            self.ids.PlayPauseButtonImage.source = not self.play and "PlayButtonW.png" or "PauseButtonW.png"

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
        self.title = 'PhoenixAnistream'

        windowManager = WindowManager()
        homeWindow = windowManager.ids.HomeWindow
        infoWindow = windowManager.ids.InfoWindow
        videoWindow = windowManager.ids.VideoWindow
        self.videoWindow = videoWindow
        homeWindow.infoWindowWidget = infoWindow
        infoWindow.videoWindow = videoWindow
        # homeWindow = HomeWindow()

        Clock.schedule_once(homeWindow.updateLatestAniData, 0)
        Clock.schedule_once(homeWindow.setWidget, -1)

        Clock.schedule_interval(homeWindow.updateVars, 1 / 30)
        Clock.schedule_interval(homeWindow.updateAniWidgets, 1 / 60)

        Clock.schedule_interval(infoWindow.refreshDescription, 1 / 60)
        # Clock.schedule_interval(infoWindow.updateVars, 1/30)
        # Clock.schedule_interval(homeWindow.pollSearchInput, 1/10)

        Clock.schedule_interval(videoWindow.refresh, 1 / 10)
        Clock.schedule_interval(videoWindow.refreshPositionSlider, 1 / 60)

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
