import os
a = Analysis(['src/main.py'],
             pathex=[os.path.abspath('.')],
             hiddenimports=['mysql.connector.locales.eng.client_error'],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='mojzesz.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True, icon='mojzesz.ico', version='.version')
