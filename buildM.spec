# -*- mode: python ; coding: utf-8 -*-
# from kivy_deps import sdl2, glew
import user_agent

block_cipher = None


a = Analysis(['main.py'],
             pathex=[],
             binaries=[],
             datas=[('AniApp.kv', '.')],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=['_tkinter', 'Tkinter', 'enchant', 'twisted'],
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
               Tree("/".join(user_agent.__file__.split("/")[:-1]), prefix='user_agent/'),
               strip=False,
               upx=True,
               upx_exclude=[],
               name='PhoenixAnistream', 
               icon=r'resources/PhoenixAniStream.ico')
               
app = BUNDLE(coll,
             name='PhoenixAnistream.app',
             icon=r'resources/PhoenixAniStream.ico',
             bundle_identifier=None)
