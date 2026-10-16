# Bundled UI fonts

Google Sans: https://github.com/googlefonts/googlesans and https://github.com/google/fonts/tree/main/ofl/googlesans
Source Han Sans (regional CN/TW subsets): https://github.com/adobe-fonts/source-han-sans/tree/release/Variable/TTF/Subset

Sources were retrieved from the official repositories on 2026-10-17. Original copyright and license files are included alongside the WOFF2 files. Google Sans uses SIL OFL 1.1 without reserved font names. Source Han Sans uses SIL OFL 1.1 with the reserved name Source.

The Chinese files are modified UI glyph subsets, renamed Memivo Han SC and Memivo Han TC in accordance with the reserved-name requirement. They derive from the SC/CN and TC/TW regional designs respectively. They do not contain every Chinese character; missing characters in personal names and filenames fall back to the matching regional system font. Google Sans is a subset with its weight axis retained and optical size 18. No online font service or system font installation is used.

Regenerate with scripts/build_ui_fonts.py after editing catalogues (development dependencies: fonttools, brotli). The original TTFs are developer inputs under ignored artifacts/font-sources and are not distributed with the app. Runtime builds use the committed WOFF2 assets.

## Original file checksums

GoogleSans.ttf: SHA-256 `d0a87d835a944b8b40d0e82a5651bb59ab97b936a2aeed5946eb57e7b2a3a90a`

SourceHanSansCN.ttf: SHA-256 `25a01e41b5cc99893eb35a6cd2cc7611841dc19eb03cbaf7f0c1de8210f2ba0b`

SourceHanSansTW.ttf: SHA-256 `cf6889f4c0f1adeaf814ca3e98cc692d9e2d706501cf7545b9b58f6e3966b6ac`
