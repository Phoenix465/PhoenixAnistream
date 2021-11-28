import queue
import threading

import kivy

kivy.require('2.0.0')  # replace with your current kivy version !

from kivy.core.window import Window

Window.size = (1280/2, 720/2)


from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import NumericProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.clock import mainthread
import os.path as path
from os import mkdir

#from kivy.loader import Loader
#Loader.loading_image = "loading.gif"

from math import ceil
import requests
from concurrent.futures import ThreadPoolExecutor

import webscraper
import sys


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


class AniWidget(RelativeLayout):
    pass


class SearchAniWidget(RelativeLayout):
    pass


class WindowManager(ScreenManager):
    pass


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

    # --- Ani Data Updater ---
    def updateVars(self, dt):
        width, height = Window.size
        self.aniWidgetWidth = height * 0.3
        self.aniWidgetHeight = height * 0.3 * 16 / 9

        self.gridCols = round(width // (height * 0.3 + 20))
        self.spacingX = (width - self.padding - self.padding - self.gridCols * self.aniWidgetWidth) / max(1, self.gridCols - 1)

        self.fontSize = height / 36

    def updateAniWidgets(self, dt, override=False):
        currentScreensize = Window.size

        if currentScreensize != self.oldScreensize or not self.firstUpdateAniWidget or override:
            self.firstUpdateAniWidget = True
            self.SearchButtonToggle(skip=True)
            self.searchInputChanged(reload=True)

            searchBox = self.ids.TextInputSearchBox
            gridLayout = self.ids.AniGridLayout if searchBox.opacity == 0 else self.ids.SearchGridLayout

            maxRows = 0
            for child in gridLayout.children:
                text = child.ids.AniLabelButton.text
                textS = text.split("\n")
                #text = "\n".join(textS[:-1])

                rowsPLengths = [len(t) * self.fontSize * 0.55 for t in textS]
                rowsLengths = [ceil(pLength / self.aniWidgetWidth) for pLength in rowsPLengths]

                rows = sum(rowsLengths)
                rows += 1

                #print(textS, rowsLengths)

                if rows > maxRows:
                    maxRows = rows

                    #print(maxRows, textS, rowsLengths)
            #print()
            self.aniWidgetHeightExtra = maxRows * (self.fontSize*1.1) - (1-self.imageSizeYOrig)*self.aniWidgetHeight/2
            self.imageSizeY = (self.imageSizeYOrig * self.aniWidgetHeight) / (self.aniWidgetHeight + self.aniWidgetHeightExtra)

            #print(repr(text))

            for child in gridLayout.children:
                child.height = self.aniWidgetHeight + self.aniWidgetHeightExtra
                child.width = self.aniWidgetWidth
                child.fontSize = self.fontSize
                child.ids.AniLabelButton.text = child.ids.AniLabelButton.text

                child.imageSizeY = self.imageSizeY

        self.oldScreensize = currentScreensize

    def updateLatestAniData(self, dt):
        self.latestAniData = webscraper.GetLatestDataAnimeDaoTo()

        gridLayout = self.ids.AniGridLayout

        gridLayout.remove_widget(self.ids.PlaceHolder)

        threadData = []

        for aniData in self.latestAniData:
            thumbnailUrl = aniData["thumbnail"]

            widget = AniWidget(width=self.aniWidgetWidth,
                               height=self.aniWidgetHeight,
                               thumbnailUrl=thumbnailUrl,
                               aniText=aniData["name"],
                               imageSizeY=self.imageSizeY,
                               episodeNumber=aniData["episode"],
                               fontSize=self.fontSize)

            gridLayout.add_widget(widget)

            threadData.append((widget.ids.Thumbnail, thumbnailUrl))

        threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True).start()

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
        #return

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

        #self.SearchButtonToggle()
        #self.SearchButtonToggle()

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
                    fontSize=self.fontSize)

                gridLayout.add_widget(widget)

                threadData.append((widget.ids.Thumbnail.__self__, thumbnailUrl))

            self.updateAniWidgets(0, override=True)

            updateThread = threading.Thread(target=self.updateImageTextures, args=(threadData,), daemon=True)
            updateThread.start()
            threading.Thread(target=self.runSearchQueue, daemon=True).start()

        searchData = webscraper.SearchDataAnimeDaoTo(searchQuery)
        genreData = webscraper.GetAnimeGenres(searchData)
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

                    if self.searchQueue.qsize() == 1 and not (self.latestSearchThread and self.latestSearchThread.is_alive):
                        self.runSearchQueue()

            else:
                if self.ScrollAniGrid.parent != self:
                    self.add_widget(self.ScrollAniGrid)

                if self.ScrollSearchGrid.parent == self:
                    self.remove_widget(self.ScrollSearchGrid)

    # --- Callback Methods ---
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

            titleAnim = Animation(x=-size[0]/2 - (size[1]*0.1*0.4)*len(titleNameWidget.text)/2*0.6, duration=duration)
            titleAnim.start(titleNameWidget)
            
            searchBoxAnim = Animation(x=size[0]*0.075, width=size[0]*0.8, opacity=1, duration=duration)
            searchBoxAnim.start(searchBox)
            searchBox.readonly = False
        else:
            searchButton.disabled = False
            searchButton.opacity = 1

            backButton.disabled = True
            backButton.opacity = 0

            titleAnim = Animation(x=-size[0]/2 + (size[1]*0.1*0.4)*len(titleNameWidget.text)/2*0.6, duration=duration)
            titleAnim.start(titleNameWidget)
                   
            searchBoxAnim = Animation(x=size[0]*0.9, width=0, opacity=0, duration=duration)
            searchBoxAnim.start(searchBox)
            searchBox.readonly = True


class AniApp(App):
    def build(self):
        windowManager = WindowManager()
        homeWindow = windowManager.ids.HomeWindow
        #homeWindow = HomeWindow()

        Clock.schedule_once(homeWindow.updateLatestAniData, 0)
        Clock.schedule_once(homeWindow.setWidget, -1)

        Clock.schedule_interval(homeWindow.updateVars, 1/30)
        Clock.schedule_interval(homeWindow.updateAniWidgets, 1/60)
        #Clock.schedule_interval(homeWindow.pollSearchInput, 1/10)

        #windowManager.current = "MainWindow"
        #self.manager.transition.direction = "left"

        return windowManager


if __name__ == '__main__':
    try:
        mkdir("cache")

    except:
        pass

    AniApp().run()
