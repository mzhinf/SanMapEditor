# 涓夊浗闇镐笟鍦板浘鎭㈠涓庣紪杈戝櫒宸ュ叿

鏈粨搴撶敤浜庨€嗗悜銆婁笁鍥介湼涓氥€婸C 鐗堢殑鍦板浘銆佽祫婧愬鍣ㄤ笌鍏冲崱璇箟鏂囦欢锛屽苟鍦ㄦ鍩虹涓婃瀯寤哄彲鍥炲啓鐨勫湴鍥剧紪杈戝櫒銆?

褰撳墠宸茬粡瀹屾垚涓ゆ潯涓荤嚎锛?

1. `stageNN.m` + `kingdom.cel/.atr` 鐨勭湡瀹炲湴鍥炬覆鏌撲笌缂栬緫鍣ㄥ師鍨嬨€?
2. `stage.ini` 鐨勪簩杩涘埗鎷嗚В銆丒xcel 瀵煎嚭锛屼互鍙婂瓧鑺傜骇 round-trip 鍥炲啓銆?

鍘熷娓告垙鏂囦欢淇濈暀鍦?[涓夊浗闇镐笟](</H:/Workstation/san/涓夊浗闇镐笟/>)锛屽垎鏋愪骇鐗╅粯璁よ緭鍑哄埌 `derived/` 鎴?`outputs/`銆?

## 褰撳墠缁撹

- `stageNN.m` 鏄湴鍥句富琛紝姣忎釜 cell 鍥哄畾 16 瀛楄妭锛屼笉鍙槸 `acwx/acwy/acwz` 涓夊眰绱㈠紩銆?
- `kingdom.cel/.atr` 鎻愪緵鍦板浘鍥惧舰璧勬簮锛屽叾涓細
  - `acwx` 鏄熀纭€鍦板舰灞傘€?
  - `acwy` 鏄彔鍔?杩囨浮灞傘€?
  - `acwz` 鏄缓绛?鐗╀欢灞傘€?
- `stage.ini` 涓嶆槸鏂囨湰 ini锛岃€屾槸鍏ㄥ眬浜岃繘鍒舵瘝琛細
  - 鏂囦欢澶达細8 瀛楄妭
  - 涓昏〃锛歚277 * 224` 瀛楄妭
  - 灏捐〃锛歚174 * 76` 瀛楄妭
- `.stg` 褰撳墠鎸夆€? 瀛楄妭澶?+ 76 瀛楄妭鍘熷璁板綍閾?+ 鍙€夊熬瀛楄妭鈥濆鐞嗭紱`stage01.stg` 宸叉寜鍘熷椤哄簭瀵煎嚭 2502 鏉¤褰曪紝灏鹃儴 48 瀛楄妭銆?
- `stage01.stg` 鏇村儚鈥滃墽鏈悕 -> 鍔垮姏鍧?-> 鍩庢睜鍧?-> 鍩庡唴姝﹀皢/澹叺/闄勫睘璁板綍鈥濈殑椤哄簭鑴氭湰锛涘綋鍓嶅眰绾у鍑哄彲寰楀埌 10 涓娍鍔?鐗规畩鍧椼€?8 涓煄姹犲潡銆?
- `city_92_family` 浠嶆槸鏈€绋崇殑鍩庡競瀛楁瀛愰泦锛?0 鏉¤褰曠殑 `city_id / city_size` 涓?`castle.txt` 20/20 瀵归綈锛涗絾瀹屾暣鍩庢睜鍧楄繕浼氳惤鍦?`text_mixed_record`銆乣city_or_structure` 绛夊亸绉诲彉浣撲腑銆?
- `uft8-game-txt/` 涓凡鏈?5 绫?txt 涓?`stage.ini` 寤虹珛浜嗙ǔ瀹氬叧鑱旓細
  - `general.txt`
  - `castle.txt`
  - `magic.txt`
  - `soldier.txt`
  - `History.txt`锛堜粎杈呭姪锛屼笉鍙備笌鑷姩鍥炲啓锛?

鏇磋缁嗙殑鏍煎紡璇存槑瑙侊細

- [鏍煎紡绗旇锛堜腑鏂囷級](docs/FORMAT_NOTES.zh.md)
- [鏂囨。缁存姢绾﹀畾](docs/DOC_WORKFLOW.zh.md)

## 鐜

鎺ㄨ崘浣跨敤 Codex bundled Python锛?

```powershell
$py = 'C:\Users\mzhinf\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

## 甯哥敤鑴氭湰

### 鍦板浘娓叉煋涓庣紪杈戝櫒

娓叉煋鐪熷疄鍦板浘锛?

```powershell
& $py tools/render_m_cel_map.py . --stage stage11 --layout stagger --layers xyz --crop 93 57 1642 1684 --scale 2
```

瀵煎嚭缂栬緫鍣?bundle锛?

```powershell
& $py tools/export_editor_bundle.py . --stage stage11
```

瀵煎嚭鍏ㄩ儴宸插彂鐜板叧鍗★細

```powershell
& $py tools/export_editor_bundle.py . --all
```

鍚姩鏈湴闈欐€佹湇鍔★細

```powershell
& $py -m http.server 8787 --bind 127.0.0.1 --directory derived/editor
```

娴忚鍣ㄥ叆鍙ｏ細

- [stage11 缂栬緫鍣╙(http://127.0.0.1:8787/stage11/editor.html)
- [缂栬緫鍣ㄧ储寮昡(http://127.0.0.1:8787/index.html)

### `stage.ini` 缁撴瀯瀵煎嚭

瀵煎嚭 `stage.ini` 缁撴瀯鍖?JSON锛?

```powershell
& $py tools/export_stage_ini_tables.py .
```

浠?JSON 鍥炲啓 `stage.ini`锛?

```powershell
& $py tools/build_stage_ini.py derived/stage_ini_analysis/stage_ini_tables.json --compare-with 涓夊浗闇镐笟\stage.ini --out derived/stage_ini_analysis/stage_roundtrip.ini
```

### `stage.ini` 涓?Excel 浜掕浆

瀵煎嚭涓や唤宸ヤ綔绨匡細

```powershell
& $py tools/export_stage_ini_txt_workbook.py .
```

浜х墿锛?

- `outputs/stage_ini_txt_analysis/stage_ini_linked_tables.xlsx`
- `outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx`

璇存槑锛?

- `linked_tables` 鏄垎鏋愮増锛屼繚鐣欏畾浣嶄笌璋冭瘯鍒椼€?
- `conversion_tables` 鏄函杞崲鐗堬紝鍙繚鐣?`row_id`銆乣title` 鍜屼笟鍔″瓧娈碉紝閫傚悎瀹為檯缂栬緫銆?

鎶婂伐浣滅翱璇诲洖 JSON锛?

```powershell
& $py tools/import_stage_ini_txt_workbook.py --input outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx --out derived/stage_ini_txt_analysis/stage_ini_conversion_import.json
```

浠?Excel 鍥炲啓鏂扮殑 `stage.ini`锛?

```powershell
& $py tools/build_stage_ini_from_txt_workbook.py outputs/stage_ini_txt_analysis/stage_ini_conversion_tables.xlsx . --out derived/stage_ini_txt_analysis/stage_ini_from_conversion_workbook.ini --compare-with 涓夊浗闇镐笟\stage.ini
```

褰撳墠宸茬粡楠岃瘉锛氭湭淇敼鐨?`stage_ini_conversion_tables.xlsx` 鍙洖鍐欏嚭涓庡師濮?`stage.ini` 瀛楄妭瀹屽叏涓€鑷寸殑鏂囦欢銆?


### `.stg` 涓?Excel 瀛楄妭绾т簰杞?

瀵煎嚭 `stage01.stg` 宸ヤ綔绨匡細

```powershell
& $py tools/export_stg_workbook.py . --stage stage01 --out outputs/stg_workbooks/stage01_stg.xlsx
```

宸ヤ綔绨垮寘鍚細

- `meta`锛? 瀛楄妭鏂囦欢澶淬€?6 瀛楄妭姝ラ暱銆佽褰曟暟銆佸熬閮ㄤ綑鏁板瓧鑺傘€?
- `raw_records`锛氭瘡鏉?76 瀛楄妭璁板綍鐨?`raw_hex` 涓?`w00..w37`锛屾槸鍥炲啓淇濆簳鏁版嵁銆?
- `hierarchy_records` / `force_city_summary`锛氬綋鍓嶆仮澶嶅嚭鐨勫娍鍔涖€佸煄姹犮€佹灏嗐€佸＋鍏甸『搴忓眰绾с€?
- `city_state`锛氬綋鍓嶅彲缂栬緫鐨勫煄姹犵姸鎬佸€欓€夊瓧娈碉紝鍖呮嫭浜哄彛銆侀噾銆佺伯銆佸紑鍙戙€佸晢涓氥€佹不瀹夈€佸潗鏍囥€佸お瀹堝€欓€夌瓑銆?
- `troop_candidates`锛氬＋鍏佃褰曞€欓€夎〃锛岀洰鍓嶅彧璇汇€?

浠庡伐浣滅翱鍥炲啓 `.stg`锛?

```powershell
& $py tools/import_stg_workbook.py outputs/stg_workbooks/stage01_stg.xlsx . --out derived/sidecar_analysis/stg_workbooks/stage01_from_workbook.stg --compare-with 涓夊浗闇镐笟\stage01.stg
```

鍙寜 `raw_records.raw_hex` 閲嶅缓锛屼笉搴旂敤 `city_state`锛?

```powershell
& $py tools/import_stg_workbook.py outputs/stg_workbooks/stage01_stg.xlsx . --out derived/sidecar_analysis/stg_workbooks/stage01_from_workbook_raw_only.stg --compare-with 涓夊浗闇镐笟\stage01.stg --no-city-state
```

褰撳墠楠岃瘉锛氭湭淇敼鐨?`stage01_stg.xlsx` 鍦ㄩ粯璁ゆā寮忓拰 `--no-city-state` 妯″紡涓嬮兘鑳藉洖鍐欏嚭涓庡師 `stage01.stg` 瀛楄妭瀹屽叏涓€鑷寸殑鏂囦欢锛涗慨鏀圭涓€涓煄姹犱汉鍙?`1200 -> 1201` 鏃跺彧浜х敓 1 涓瓧鑺傚樊寮傘€?

### `.stg` Phase 7 瀵圭収瀵煎嚭

瀵煎嚭鍗曚釜鍏冲崱鐨?`.stg` 鍘熷璁板綍閾撅細

```powershell
& $py tools/export_stg_raw_chain.py . --stage stage01
```

浜х墿锛?

- `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.json`
- `derived/sidecar_analysis/raw_chain/stage01/stg_raw_chain.csv`

瀵煎嚭鎸夊師濮嬮『搴忔仮澶嶇殑鍔垮姏/鍩庢睜灞傜骇锛?

```powershell
& $py tools/export_stg_hierarchy.py . --stage stage01
```

浜х墿锛?

- `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy.json`
- `derived/sidecar_analysis/hierarchy/stage01/stg_hierarchy_records.csv`
- `derived/sidecar_analysis/hierarchy/stage01/stg_force_city_summary.csv`

鐢ㄩ€旓細

- 灏?`.stg` 鐪嬫垚椤哄簭璁板綍閾撅紝鎭㈠鈥滃娍鍔?-> 鍩庢睜 -> 姝﹀皢/澹叺鈥濈殑鍙缁撴瀯銆?
- 鐢?`castle.txt`銆乣History.txt` 浜ゅ弶楠岃瘉鍩庢睜鍚嶃€佹灏嗗悕涓?id 绌洪棿銆?
- 閬垮厤鎶婃棫鑴氭湰鐨?`slot/context_owner_slot_consensus` 褰撴垚宸茬‘璁?owner 瀛楁锛涘畠浠彧淇濈暀涓哄巻鍙叉帓鏌ョ嚎绱€?

瀵煎嚭鍩庢睜鐘舵€佷笌澹叺璁板綍鍊欓€夎〃锛?

```powershell
& $py tools/export_stg_city_troop_analysis.py . --stage stage01
```

浜х墿锛?

- `derived/sidecar_analysis/city_troop/stage01/stg_city_troop_candidates.json`
- `derived/sidecar_analysis/city_troop/stage01/city_state_candidates.csv`
- `derived/sidecar_analysis/city_troop/stage01/troop_candidates.csv`

鐢ㄩ€旓細鎶婂煄姹犲ご閮ㄦ寜 `city_id` 浣嶇疆灞曞紑涓轰汉鍙ｃ€侀噾銆佺伯銆佸紑鍙戙€佸晢涓氥€佹不瀹夈€佷笂闄愩€佸潗鏍囥€佸お瀹堝€欓€夊瓧娈碉紱澹叺璁板綍鎸?`224` 閿氱偣灞曞紑骞舵寕鍥炴墍灞炲煄姹犮€?

瀵煎嚭鍗曚釜鍏冲崱鐨勬棫鐗堝瓧娈靛鐓ц〃锛?

```powershell
& $py tools/export_stg_phase7_links.py . --stage stage01
```

浜х墿锛?

- `derived/sidecar_analysis/phase7/stage01/stg_phase7_links.json`
- `derived/sidecar_analysis/phase7/stage01/general_rows.csv`
- `derived/sidecar_analysis/phase7/stage01/faction_rows.csv`
- `derived/sidecar_analysis/phase7/stage01/city_rows.csv`

鐢ㄩ€旓細缁х画妫€鏌?`224 / 96 / 92` 閿氱偣褰掍竴鍖栧悗鐨勫瓧娈靛€欓€夊€笺€?


## 娴嬭瘯

杩愯 `.stg` 涓?Excel 浜掕浆鍥炲綊娴嬭瘯锛?

```powershell
& $py -m unittest tools.test_stg_workbook_roundtrip
```

璇ユ祴璇曚細涓存椂瀵煎嚭 `stage01.stg` 宸ヤ綔绨匡紝骞堕獙璇侊細

- 瀵煎嚭鐨勫伐浣滅翱鍖呭惈 `meta/raw_records/city_state/troop_candidates` 绛夊繀瑕?sheet銆?
- 榛樿瀵煎叆妯″紡鑳藉洖鍐欏嚭涓庡師 `.stg` 瀛楄妭瀹屽叏涓€鑷寸殑鏂囦欢銆?
- `--no-city-state` 瀵瑰簲鐨?raw-only 璺緞鑳藉瓧鑺傜骇 round-trip銆?
- 淇敼 `city_state` 涓殑鍩庢睜浜哄彛鍚庯紝鍙鐩栭鏈熺殑 u16 瀛楁銆?

## 鏂囨。缁存姢绾﹀畾

浠庣幇鍦ㄥ紑濮嬶紝鏈」鐩寜鍥哄畾瑙勫垯缁存姢鏂囨。锛屼笉鍐嶁€滀唬鐮佸厛璧般€佹枃妗ｈˉ涓嶈ˉ鐪嬫儏鍐碘€濓細

1. 浜岃繘鍒剁粨鏋勫彉鍖栵細鍚屾鏇存柊 [docs/FORMAT_NOTES.zh.md](/H:/Workstation/san/docs/FORMAT_NOTES.zh.md)銆?
2. 鑴氭湰鐢ㄦ硶鍙樺寲锛氬悓姝ユ洿鏂?[README.md](/H:/Workstation/san/README.md)銆?
3. 闃舵鐩爣鍙樺寲锛氬悓姝ユ洿鏂?[task_plan.md](/H:/Workstation/san/task_plan.md)銆?
4. 鏂扮粨璁烘垨鏂拌瘉鎹細鍚屾鏇存柊 [findings.md](/H:/Workstation/san/findings.md)銆?
5. 鏈鍋氫簡浠€涔堛€佹€庝箞楠岃瘉锛氬悓姝ユ洿鏂?[progress.md](/H:/Workstation/san/progress.md)銆?
6. 鎻愪氦 git 鍓嶏紝鑷冲皯妫€鏌ヤ竴娆♀€滄枃妗ｆ槸鍚︿粛鑳芥寚瀵兼柊浜哄鐜板綋鍓嶇粨鏋溾€濄€?

瀹屾暣娴佺▼瑙?[docs/DOC_WORKFLOW.zh.md](/H:/Workstation/san/docs/DOC_WORKFLOW.zh.md)銆?

## 涓嬩竴姝ヨ鍒?

褰撳墠鏈€鍊煎緱鍋氱殑 3 浠朵簨锛?

1. 缁х画閫嗗悜 `stageNN.stg`锛屾妸灞傜骇鍧楀啓鍥炶兘鍔涖€佺洿鎺?owner 瀛楁銆佸＋鍏垫暟閲?鍏电瀛楁閫愭鎷嗘竻銆?
2. 缁х画閫嗗悜 `stageNN.evt`锛岀‘璁や簨浠惰褰曞浣曞紩鐢ㄥ湴鍥惧潗鏍囥€佸璞″拰鍏ㄥ眬 id銆?
3. 浠?`Emperor.exe` 缁х画纭 `.s/.x` 鐨勭敓鎴愬拰璇诲彇璺緞锛屾妸灏忓湴鍥?缂撳瓨鍐欏洖琛ラ綈鍒扮紪杈戝櫒閾捐矾銆?


### 2026-06-30：士兵记录编码簇补充

- `tools/export_stg_city_troop_analysis.py` 现在会在多 `224` 命中时结合兵种文本与 `soldier.txt` 选择最佳锚点。
- `troop_candidates` 新增 `troop_text_normalized`、`expected_soldier_id_from_text`、`candidate_soldier_id_t22`、`candidate_soldier_code_plus200_t12`、`candidate_soldier_code_plus97_t14`。
- 当前已确认：`t22` 对应 `soldier.txt` 的小兵种 id，且 `t12 = t22 + 200`、`t14 = t22 + 97`。
- 新增测试：`& $py -m unittest tools.test_stg_troop_analysis`

### 2026-06-30：troop block 归一化补充

- `.stg` 里的士兵槽位不应只看单条 76 字节记录；当前样本显示，单个 troop slot 更像“1 条 troop_entry + 3 条后续 binary/zero 记录”的 4-record block。
- `tools/export_stg_city_troop_analysis.py` 已新增 block 视角字段：`troop_block_normalization_method`、`block_candidate_soldier_id_w22`、`block_candidate_soldier_code_plus200_w12`、`block_candidate_soldier_code_plus97_w14`、`block_candidate_enabled_flag_w24`、`block_candidate_value50_w26`、`block_candidate_value50_w32` 等。
- `stage01` 里 42 条 troop 记录中，有 40 条能通过“第一条记录中的第一个 224”稳定归一化为同一 block 模板；该视角明显比单记录视角更稳。
- 当前最稳的 block 模板结论：`w12 = soldier_id + 200`、`w14 = soldier_id + 97`、`w22 = soldier_id`，并常见 `w24 in {0,1}`、`w26 = 50`、`w32 = 50`。
- 新增测试仍通过：`& $py -m unittest tools.test_stg_troop_analysis` 与 `& $py -m unittest tools.test_stg_workbook_roundtrip`
