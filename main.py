import threading

import kivy

kivy.require('2.0.0')  # replace with your current kivy version !

from kivy.core.window import Window

Window.size = (1280/2, 720/2)


from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import NumericProperty
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


class AniWidget(RelativeLayout):
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

    def updateVars(self, dt):
        width, height = Window.size
        self.aniWidgetWidth = height * 0.3
        self.aniWidgetHeight = height * 0.3 * 16 / 9

        self.gridCols = round(width // (height * 0.3 + 20))
        self.spacingX = (width - self.padding - self.padding - self.gridCols * self.aniWidgetWidth) / max(1, self.gridCols - 1)

        self.fontSize = height / 36

    def updateAniWidgets(self, dt):
        currentScreensize = Window.size

        if currentScreensize != self.oldScreensize or True:
            gridLayout = self.ids.AniGridLayout

            maxRows = 0
            for child in gridLayout.children:
                text = child.ids.AniLabelButton.text
                textS = text.split("\n")
                text = "\n".join(textS[:-1])

                textPLength = len(text) * self.fontSize * 0.4
                rows = ceil(textPLength / self.aniWidgetWidth)
                rows += 1

                if rows > maxRows:
                    maxRows = rows

            self.aniWidgetHeightExtra = maxRows * (self.fontSize*1.1) - (1-self.imageSizeYOrig)*self.aniWidgetHeight/2
            self.imageSizeY = (self.imageSizeYOrig * self.aniWidgetHeight) / (self.aniWidgetHeight + self.aniWidgetHeightExtra)

            #print(repr(text))

            for child in gridLayout.children:
                child.height = self.aniWidgetHeight + self.aniWidgetHeightExtra
                child.width = self.aniWidgetWidth
                child.fontSize = self.fontSize

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
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = executor.map(self.updateImageTexture, values)

        forceGeneration = list(results)


class AniApp(App):
    def build(self):
        homeWindow = HomeWindow()
        Clock.schedule_interval(homeWindow.updateVars, 1/30)
        Clock.schedule_interval(homeWindow.updateAniWidgets, 1/10)
        Clock.schedule_once(homeWindow.updateLatestAniData, 0)

        return homeWindow


if __name__ == '__main__':
    try:
        mkdir("cache")

    except:
        pass

    AniApp().run()
