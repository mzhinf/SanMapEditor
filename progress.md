# Progress Log

## 2026-06-23

- 鐩樼偣娓告垙鐩綍锛岀‘璁?`stageNN.*`銆乣kingdom.cel/.atr`銆丏AT 瀹瑰櫒涓?`Emperor.exe` 涓烘牳蹇冨璞°€?
- 纭 `.m` 鏂囦欢澶翠负 `width + height + Hello1.0`锛宑ell 璁板綍鍥哄畾 16 瀛楄妭銆?
- 瀹屾垚 `kingdom.cel/.atr` 鐨勭涓€杞浘灞傛媶瑙ｃ€?
- 鎭㈠鍩轰簬 `acwx/acwy/acwz` 鐨勭湡瀹炲湴鍥炬覆鏌撱€?
- 浠?`Emperor.exe` 鏀跺彛 `stage11` 鎵€闇€鐨?world-to-screen 鍙樻崲銆?
- 寤虹珛娴忚鍣ㄥ湴鍥剧紪杈戝櫒鍘熷瀷锛屾敮鎸?Inspect / Paint / 鏈湴 `.m` 鍔犺浇 / Undo / Reset / patch 瀵煎嚭銆?

## 2026-06-24

- 琛ラ綈缂栬緫鍣ㄨ祫婧愰潰鏉裤€佸嵆鏃堕噸缁樸€佸彸閿嫋鍔ㄥ湴鍥俱€佹柟鍚戦敭绉诲姩閫変腑鏍笺€?
- 瀹屾垚瀹夊叏 patch -> `.m` 澶嶅埗鍐欏洖鑴氭湰銆?
- 寤虹珛 `.stg/.evt/.spr/.dor/.s/.x` 鐨勭涓€杞?sidecar 鍒嗘瀽鑴氭湰涓庡伐浣滅翱瀵煎嚭銆?
- 淇 `docs/FORMAT_NOTES.zh.md` 涓殑涓枃缂栫爜姹℃煋涓€娆★紝浣嗗悗缁張鍙戠幇鍏朵綑鏂囨。浠嶆湁娈嬬暀姹℃煋銆?
- 纭 `stage.ini` 鍙鍑?JSON / Excel锛屽苟鍙粠 JSON 鍥炲啓瀛楄妭绾т竴鑷存枃浠躲€?

## 2026-06-25

- 閲嶅仛 `uft8-game-txt` 涓?`stage.ini` 鐨勫叧鑱旀柟寮忥紝鏀逛负鍩轰簬鍘熷 dword 娴侊紝鑰屼笉鏄厛淇′换 `family_guess`銆?
- 纭褰撳墠绋冲畾鏄犲皠锛?
  - `general.txt`锛氭闀?`57 dwords`
  - `castle.txt`锛氭闀?`25 dwords`
  - `magic.txt`锛氭闀?`19 dwords`
  - `soldier.txt`锛氭闀?`20 dwords`
- 鍖哄垎鍒嗘瀽鐗堝伐浣滅翱涓庣函杞崲鐗堝伐浣滅翱銆?
- 鏂板绾?Python 鐨?Excel 瀵煎嚭銆佸鍏ャ€佸洖鍐欓摼璺細
  - `tools/export_stage_ini_txt_workbook.py`
  - `tools/import_stage_ini_txt_workbook.py`
  - `tools/build_stage_ini_from_txt_workbook.py`
- 淇 Python 瀵煎嚭 `xlsx` 鏃剁殑闈炴硶 XML 鎺у埗瀛楃闂銆?
- 楠岃瘉缁撴灉锛?
  - `stage_ini_linked_tables.xlsx` 鍙敱 Python 姝ｅ父瀵煎嚭
  - `stage_ini_conversion_tables.xlsx` 鍙敱 Python 姝ｅ父瀵煎嚭
  - 鏈慨鏀圭殑 `stage_ini_conversion_tables.xlsx` 鍙洖鍐欎负涓庡師濮?`stage.ini` 瀹屽叏涓€鑷寸殑鏂版枃浠?
  - `sha256 = 29584de26770323a09849d180331d936e9c112f55936d76b08f4f6f6a63663b8`
- 鏂板骞朵慨姝?`.stg` 瀵煎嚭閾捐矾锛?
  - `tools/export_stg_phase7_links.py`锛氫繚鐣欐棫鐗?`224 / 96 / 92` 瀛楁褰掍竴鍖栧鐓с€?
  - `tools/export_stg_raw_chain.py`锛氱洿鎺ユ寜鍘熷 76 瀛楄妭 stride 瀵煎嚭瀹屾暣璁板綍閾撅紝涓嶅啀璺宠繃鏃犳枃鏈褰曘€?
  - `tools/export_stg_hierarchy.py`锛氭寜鍘熷椤哄簭鎭㈠鍔垮姏/鍩庢睜/姝﹀皢/澹叺灞傜骇銆?
- 瀵煎嚭 `stage01` 鏂颁骇鐗╋細
  - `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.json`
  - `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.csv`
  - `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy.json`
  - `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy_records.csv`
  - `derived/sidecar_analysis/hierarchy/stage01/stg_force_city_summary.csv`
- `stage01.stg` 褰撳墠楠岃瘉缁撴灉锛?
  - 鏂囦欢涓?8 瀛楄妭澶淬€?502 鏉″畬鏁?76 瀛楄妭璁板綍銆?8 瀛楄妭灏鹃儴銆?
  - 灞傜骇瀵煎嚭寰楀埌 10 涓娍鍔?鐗规畩鍧椼€?8 涓煄姹犲潡銆?6 鏉℃灏嗚褰曘€?2 鏉″＋鍏佃褰曘€?
  - 鍙缁撴瀯渚嬪瓙锛歚鍔夊倷 -> 骞冲師`銆乣鏇规搷 -> 闄崇暀`銆乣瀛爡 -> 闀锋矙`銆乣鍔夎〃 -> 瑗勯櫧/姹熷/姹熼櫟`銆乣涓珛鍦?-> 瑗勫钩/鍖楀钩/钖?...`銆?
  - `city_92_family` 浠嶆湁 20 鏉¤褰曞叏閮ㄥ涓?`castle.txt` 鐨?`city_id / city_size`銆?
  - `context_prev_slot / context_next_slot / context_owner_slot_consensus` 宸查檷绾т负鏃х増鎺掓煡绾跨储锛屼笉鍐嶅綋浣?owner 缁撹銆?
- 鏂板 `tools/export_stg_city_troop_analysis.py`锛屽鍑哄煄姹犵姸鎬佸瓧娈典笌澹叺璁板綍鍊欓€夎〃锛?
  - `derived/sidecar_analysis/city_troop/stage01/stg_city_troop_candidates.json`
  - `derived/sidecar_analysis/city_troop/stage01/city_state_candidates.csv`
  - `derived/sidecar_analysis/city_troop/stage01/troop_candidates.csv`
- `stage01.stg` 鍩庢睜鐘舵€佸瓧娈甸獙璇佺粨鏋滐細
  - `city_id / city_size / map_x / map_y` 鍏ㄩ儴 38/38 瀵归綈 `castle.txt`銆?
  - `city_id+6/+8/+10` 楂樼疆淇″搴斿綋鍓嶄汉鍙?閲?绮€?
  - `city_id+14/+16/+18` 楂樼疆淇″搴斿紑鍙?鍟嗕笟/娌诲畨銆?
  - `city_id+20/+22/+24` 楂樼疆淇″搴斾笁椤逛笂闄愩€?
  - `city_id+30` 鏄お瀹?鍩庝富姝﹀皢 id 鍊欓€夛紝23 鏉¤兘鏄犲皠 `History.txt`锛屽叾涓?22 鏉″湪鏈煄姝﹀皢鍒楄〃鍐呫€?
  - 42 鏉″＋鍏佃褰曞凡鎸傚洖鍩庢睜锛屼絾鏁伴噺/绛夌骇瀛楁浠嶆湭鏈€缁堝懡鍚嶃€?

## 鏈鏂囨。鏀跺彛锛堝凡瀹屾垚锛?

- `README.md` 宸查噸鍐欎负骞插噣 UTF-8 涓枃鐗堟湰銆?
- `docs/FORMAT_NOTES.zh.md` 宸查噸鍐欙紝骞跺崟鍒?`stage.ini` 浜岃繘鍒舵瀯鎴愩€?
- 鏂板 `docs/DOC_WORKFLOW.zh.md`锛屾妸鏂囨。鏇存柊璐ｄ换鍜屾彁浜ゅ墠妫€鏌ヨ〃鍐欐銆?
- `task_plan.md`銆乣findings.md`銆乣progress.md` 宸插悓姝ヤ负鏂扮殑鏈夋晥鍩虹嚎銆?
- 鏈疆缁х画鎶?`.stg Phase 7` 鐨勬柊缁撹鍚屾鍐欏洖鏂囨。锛岄伩鍏嶅彧鍋滅暀鍦ㄨ亰澶╀笂涓嬫枃銆?
- 楠岃瘉锛歅ython 鎸?UTF-8 璇诲彇涓婅堪鏂囨。鎴愬姛锛岀‘璁や贡鐮佹潵鑷帶鍒跺彴浠ｇ爜椤佃€岄潪鏂囦欢鍐呭銆?

## 楠岃瘉璁板綍

| 椤圭洰 | 缁撴灉 |
| --- | --- |
| `stage.ini` JSON -> binary 鍥炲啓 | 瀛楄妭绾т竴鑷?|
| `stage_ini_conversion_tables.xlsx -> stage.ini` 鍥炲啓 | 瀛楄妭绾т竴鑷?|
| 缂栬緫鍣ㄦ湰鍦?`.m` 鍔犺浇 | 閫氳繃 |
| 缂栬緫鍣?patch 鍐欏洖澶嶅埗浠?| 閫氳繃 |
| 鏍稿績鏂囨。 UTF-8 璇诲彇 | 閫氳繃 |
| `stage01.stg city_id -> castle.txt` 瀵归綈 | 20/20 閫氳繃 |
| `stage01.stg city_size -> castle.txt` 瀵归綈 | 20/20 閫氳繃 |
| `stage01.stg` 鍘熷璁板綍閾惧鍑?| 2502 鏉¤褰?+ 48 瀛楄妭灏鹃儴锛岄€氳繃 |
| `stage01.stg` 灞傜骇瀵煎嚭 | 10 涓娍鍔?鐗规畩鍧椼€?8 涓煄姹犲潡锛岄€氳繃 |
| `stage01.stg` 鍩庢睜鐘舵€佸瓧娈?| `city_id/city_size/x/y` 38/38 瀵归綈锛岄€氳繃 |

## 褰撳墠椋庨櫓

1. `.stg` 鐩存帴 owner 瀛楁浠嶆湭閿佸畾锛屽綋鍓嶄紭鍏堟寜椤哄簭灞傜骇瑙ｉ噴鎵€灞炲叧绯汇€?
2. 澹叺璁板綍涓殑鏁伴噺銆佺瓑绾с€佸叺绉?id 瀛楁浠嶉渶缁х画鍛藉悕銆?
3. `.evt` 浠嶆湭瀹屾垚瀛楁鍛藉悕锛屾殏鏃朵笉鑳藉仛瀹屾暣璇箟缂栬緫鍣ㄣ€?
4. `.s/.x` 鐨勫啓鍥炴祦绋嬪皻鏈‘璁わ紝涓嶅簲璐哥劧鐢熸垚瑕嗙洊銆?
5. `acwz` 鐨勫畬鏁?footprint / z-order 浠嶆湁灏惧樊銆?

## 2026-06-25 `.stg` Excel 浜掕浆鏀跺彛

- 鏂板 `.stg` Excel 浜掕浆鑴氭湰锛?
  - `tools/export_stg_workbook.py`锛氬鍑?`meta/raw_records/hierarchy_records/force_city_summary/city_state/troop_candidates`銆?
  - `tools/import_stg_workbook.py`锛氫粠 workbook 鍥炲啓 `.stg`锛岄粯璁ゅ簲鐢?`city_state`锛屼篃鏀寔 `--no-city-state` raw-only 閲嶅缓銆?
- 琛ュ厖 `docs/FORMAT_NOTES.zh.md` 鐨?`.stg` 瀛楄妭绾ф瀯鎴愪笌杞崲鑴氭湰濂戠害锛屽啓鏄?header銆乺ecord銆乼ail銆乻heet銆佸洖鍐欏叕寮忓拰楠岃瘉缁撴灉銆?
- 鏇存柊 `README.md` 鐨?`.stg` 浜掕浆浣跨敤鎸囧崡銆?
- 楠岃瘉缁撴灉锛?
  - 榛樿妯″紡锛歚stage01_stg.xlsx -> stage01_from_workbook.stg` 涓庡師 `stage01.stg` 瀛楄妭瀹屽叏涓€鑷淬€?
  - `--no-city-state`锛氬悓鏍峰瓧鑺傚畬鍏ㄤ竴鑷淬€?
  - 缂栬緫鐑熸祴锛氱涓€涓煄姹犱汉鍙?`1200 -> 1201` 鍚庝粎 1 涓瓧鑺傚彉鍖栵紝鍋忕Щ `0x1A4`銆?

## 2026-06-29 `.stg` Excel 浜掕浆娴嬭瘯

- 鏂板 `tools/test_stg_workbook_roundtrip.py`锛岀敤 `unittest` 瑕嗙洊 `.stg -> Excel -> .stg` 鐨勬牳蹇冨洖褰掕矾寰勩€?
- 娴嬭瘯鐐瑰寘鎷細宸ヤ綔绨垮繀瑕?sheet 涓?meta銆侀粯璁ゅ鍏ュ瓧鑺備竴鑷淬€乺aw-only 瀛楄妭涓€鑷淬€佺紪杈?`city_state.candidate_population` 鍚庡彧鏀归鏈?u16 瀛楁銆?
- 淇 `tools/stage_ini_excel_codec.py`锛氳鍙?鍐欏叆 workbook 鍚庢樉寮忓叧闂?openpyxl 鍙ユ焺锛岄伩鍏?Windows 涓婃祴璇曟竻鐞嗘垨鍚庣画鎵瑰鐞嗛亣鍒版枃浠堕攣銆?
- 楠岃瘉鍛戒护锛歚& $py -m unittest tools.test_stg_workbook_roundtrip`锛岀粨鏋?`Ran 4 tests ... OK`銆?

## 2026-06-30 缂栬緫鍣ㄦ€ц兘浼樺寲

- 妫€鏌?`tools/editor_app.html` 鍚庣‘璁ゅ崱椤夸富鍥狅細鍗曟牸缂栬緫瑙﹀彂鍏ㄥ浘涓夊眰閲嶇粯銆佷晶鏍忕粺璁℃瘡娆″叏琛ㄦ壂鎻忋€佹嫋鍔?缂╂斁鐩存帴鍦ㄩ珮棰戜簨浠朵腑閲嶇粯銆?
- 缂栬緫鍣ㄦā鏉挎柊澧?`requestAnimationFrame` 鍚堝抚缁樺埗銆乴ayer stats 缂撳瓨銆佹寜鑴忓尯鍩熷眬閮ㄩ噸缁樸€?
- `paint` 妯″紡鐐瑰嚮涓嶅啀鍦?`applyPaint()` 涔嬪悗閲嶅鎵ц涓€娆?`refreshSide()/draw()`銆?
- 宸插皢妯℃澘鍚屾澶嶅埗鍒扮幇鏈?`derived/editor/*/editor.html`锛屽綋鍓嶆墦寮€鐨?`stage11/editor.html` 鍒锋柊鍚庡嵆鍙娇鐢ㄦ柊閫昏緫銆?
- 楠岃瘉锛氭娊鍙栬剼鏈潡鍚庣敤 `node --check` 閫氳繃璇硶妫€鏌ャ€?

## 2026-06-30 `.stg` 士兵记录锚点与兵种 id

- 修正 `tools/export_stg_city_troop_analysis.py`：不再把“第一个 224”当作唯一真锚点，而是在多 `224` 命中时结合兵种文本与 `soldier.txt` 评分选择最佳旋转。
- 新增 `troop_text_normalized`、`expected_soldier_id_from_text`、`candidate_soldier_id_t22`、`candidate_soldier_code_plus200_t12`、`candidate_soldier_code_plus97_t14` 等字段，把兵种 id 编码簇单独导出。
- 确认 `.stg` 士兵简称应映射到 `soldier.txt` 的小兵种原型；已锁定 `t22 = soldier_id`、`t12 = soldier_id + 200`、`t14 = soldier_id + 97`。
- 重写 `tools/export_stg_workbook.py` 中受旧乱码污染的说明文本，并同步适配 `build_troop_rows(root, ...)` 新签名。
- 新增 `tools/test_stg_troop_analysis.py`，覆盖多 `224` 锚点选择和 `stage01` 士兵 id 编码簇导出。
- 验证：
  - `python.exe -m unittest tools.test_stg_troop_analysis` -> `Ran 2 tests ... OK`
  - `python.exe -m unittest tools.test_stg_workbook_roundtrip` -> `Ran 4 tests ... OK`
