import kivy

kivy.require('2.0.0')  # replace with your current kivy version !

from kivy.core.window import Window

Window.size = (1280/2, 720/2)


from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import NumericProperty, ListProperty
from kivy.clock import Clock

from kivy.loader import Loader
Loader.loading_image = "loading.gif"

import webscraper


class AniWidget(RelativeLayout):
    pass


class HomeWindow(Widget):
    padding = NumericProperty(20)
    spacingX = NumericProperty(10)
    aniWidgetWidth = NumericProperty(Window.size[1] * 0.3)
    aniWidgetHeight = NumericProperty(Window.size[1] * 0.3 * 16 / 9)
    gridCols = NumericProperty(1)
    latestAniData = ListProperty([])

    oldScreensize = Window.size

    def updateVars(self, dt):
        width, height = Window.size
        self.aniWidgetWidth = height * 0.3
        self.aniWidgetHeight = height * 0.3 * 16 / 9

        self.gridCols = round(width // (height * 0.3 + 20))
        self.spacingX = (width - self.padding - self.padding - self.gridCols * self.aniWidgetWidth) / max(1, self.gridCols - 1)

    def updateAniWidgets(self, dt):
        currentScreensize = Window.size

        if currentScreensize != self.oldScreensize:
            gridLayout = self.ids.AniGridLayout

            for child in gridLayout.children:
                child.height = self.aniWidgetHeight
                child.width = self.aniWidgetWidth

        self.oldScreensize = currentScreensize

    def updateLatestAniData(self, dt):
        self.latestAniData = webscraper.GetLatestDataAnimeDaoTo()

        gridLayout = self.ids.AniGridLayout

        gridLayout.remove_widget(self.ids.PlaceHolder)

        for aniData in self.latestAniData:
            thumbnailUrl = aniData["thumbnail"]

            gridLayout.add_widget(AniWidget(width=self.aniWidgetWidth,
                                            height=self.aniWidgetHeight,
                                            thumbnailUrl=thumbnailUrl,
                                            aniText=aniData["name"],
                                            episodeNumber=aniData["episode"]))


class AniApp(App):
    def build(self):
        homeWindow = HomeWindow()
        Clock.schedule_interval(homeWindow.updateVars, 1/30)
        Clock.schedule_interval(homeWindow.updateAniWidgets, 1/10)
        Clock.schedule_once(homeWindow.updateLatestAniData, 0)

        return homeWindow


if __name__ == '__main__':
    AniApp().run()
