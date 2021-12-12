from kivy.app import App
from kivy.uix.video import Video


class VideoWindow(App):
    def build(self):
        # Note delete the gphstream

        video = Video(source=r"https://www201.sbcdnvideo.com/tysxegnl2666j6cdaatbrhcsfg2mvmk43rkntgcxbpkjjo6cjqrfrrstboiq/sword-art-online-episode-1.mp4")

        video.state = "play"
        video.options = {"eos": "loop"}
        video.allow_stretch = True

        return video


if __name__ == "__main__":
    window = VideoWindow()
    window.run()
