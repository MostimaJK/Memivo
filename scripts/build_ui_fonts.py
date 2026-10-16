"""Development-only font subsetting; requires fonttools and brotli.

Sources are documented in frontend/src/assets/fonts/NOTICE.md.
Run after changing the locale catalogues. No font downloads occur at app startup.
"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'artifacts/font-sources'
    destination = ROOT / 'frontend/src/assets/fonts'
    texts = ''.join(path.read_text(encoding='utf-8') for path in (ROOT/'frontend/src/locales').glob('*.json'))
    texts += (ROOT/'frontend/src/main.tsx').read_text(encoding='utf-8')
    texts += '简体中文繁體中文思源黑体思源黑體照片相片未知人物界面验证'
    characters = {ord(c) for c in texts} | set(range(32, 0x250)) | set(range(0x2000, 0x2070))
    for filename, output, family in [
        ('GoogleSans.ttf', 'google-sans.woff2', 'Google Sans'),
        ('SourceHanSansCN.ttf', 'memivo-han-sc.woff2', 'Memivo Han SC'),
        ('SourceHanSansTW.ttf', 'memivo-han-tc.woff2', 'Memivo Han TC')
    ]:
        font = TTFont(source / filename)
        options = subset.Options()
        options.name_IDs = ['*']
        options.name_legacy = True
        options.name_languages = ['*']
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=characters)
        subsetter.subset(font)
        if filename.startswith('Google'):
            font = instantiateVariableFont(font, {'GRAD': 0, 'opsz': 18}, inplace=True)
        # Adobe reserves the name "Source" for unmodified fonts. Rename the UI subset.
        if filename.startswith('Source'):
            for record in font['name'].names:
                if record.nameID in (1, 4, 6, 16):
                    value = family.replace(' ', '') if record.nameID == 6 else family
                    record.string = value.encode(record.getEncoding())
                elif record.nameID == 3 or record.nameID >= 256:
                    value = record.toUnicode().replace('SourceHanSansCNVF', 'MemivoHanSCVF').replace('SourceHanSansTWVF', 'MemivoHanTCVF')
                    record.string = value.encode(record.getEncoding())
        font.flavor = 'woff2'
        font.save(destination/output)
        print(output, (destination/output).stat().st_size)


if __name__ == '__main__':
    main()
