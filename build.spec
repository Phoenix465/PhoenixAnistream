# -*- mode: python ; coding: utf-8 -*-
from kivy_deps import sdl2, glew
import user_agent
import ffpyplayer
FFPYPLAYER_PATH = ffpyplayer.__path__[0]

block_cipher = None


a = Analysis(['main.py'],
             pathex=[],
             binaries=[
                  (f'{FFPYPLAYER_PATH}\\*.pyd', 'ffpyplayer'),
                 (f'{FFPYPLAYER_PATH}\\player\\*.pyd', 'ffpyplayer/player'),
             ],
             datas=[('AniApp.kv', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, 
          [],
          exclude_binaries=True,
          name='PhoenixAnistream',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None , 
          icon='resources/PhoenixAniStream.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas, 
               Tree('resources/', prefix='resources/'),
               Tree("\\".join(user_agent.__file__.split("\\")[:-1]), prefix='user_agent/'),
               *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
               strip=False,
               upx=True,
               upx_exclude=[],
               name='PhoenixAnistream', 
               icon=r'resources/PhoenixAniStream.ico')
