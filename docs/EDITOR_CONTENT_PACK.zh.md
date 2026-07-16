# 地图编辑器独立内容包

独立内容包用于把一次性解析、渲染后的关卡素材与编辑器程序分离。基础 Windows 发布包仍保持五文件无资源结构；用户可以单独选择内容包，也可以使用包含 `content-packs/` 的组合分发包。

## 一、文件格式

内容包扩展名为 `.sanmap-pack`，底层是 ZIP，格式标识为 `san-map-editor-content-pack-v1`：

```text
stage01.sanmap-pack
├── manifest.json
└── content/
    └── stage01/
        ├── stage.json
        ├── resources.json
        ├── map.png
        ├── minimap.png
        ├── heads.png
        ├── draw_acw*.png
        ├── resources_acw*.png
        └── 写回所需参考文件
```

内容包不得包含 `editor.html`、`index.html`、`index.json` 或 `release-info.json`。启动器始终使用当前 EXE 内嵌的 `editor_app.html` 生成缓存入口，因此升级程序后不需要重新生成地图素材。

`manifest.json` 记录内容 Schema、关卡、来源文件的非路径摘要，以及每个内容文件的相对路径、字节数和 SHA-256。来源摘要不记录用户本机绝对路径。

## 二、生成内容包

准备与 `stageXX.m` 同目录的完整输入文件，然后执行：

```powershell
python -m san_tools run build-editor-content-pack path\to\stage01.m `
  --output-dir dist\content-packs
```

生成过程会执行与原始文件导入相同的严格校验，并在输出目录内部创建事务工作目录。成功后得到 `stage01.sanmap-pack`；工作目录会自动清理。

内容包会保留导出 `.dor/.stg/stage.ini/History.txt/heads.dat` 所需的用户参考文件，因此仍属于用户生成的游戏数据，不应在未确认权利的情况下公开分发。

## 三、启动载入

有三种载入方式：

1. 在启动器点击“选择内容包”。
2. 使用 `SanMapEditor.exe --content-pack path\to\stage01.sanmap-pack`。
3. 把一个内容包放在 EXE 同级的 `content-packs/`；启动器发现恰好一个内容包时自动载入。

存在多个随包内容包时，启动器不会静默选择，会提示用户点击“选择内容包”。

启动器在载入前检查：

- ZIP 路径穿越、盘符路径、反斜杠和重复条目；
- Manifest 格式、Schema、关卡目录和文件集合；
- 文件数量、单文件大小和总展开大小上限；
- 每个文件的字节数与 SHA-256；
- `stage.json`、`resources.json` 的关卡和本地资源引用；
- 禁止内容包携带编辑器代码或外部资源 URL。

## 四、持久哈希缓存

内容包首次载入后解包到：

```text
%LOCALAPPDATA%\SanMapEditor\content-cache\<内容包 SHA-256>\
```

相同内容包再次载入时复用缓存，不重新解析或渲染游戏文件。启动器仍会重新审计内容包，并刷新当前版本的 `editor.html` 与 `release-info.json`。关闭启动器只停止本机服务，不删除内容缓存。

原始游戏文件导入仍使用 `%TEMP%/SanMapEditor` 事务会话，并在关闭时清理；两种生命周期不得混用。

## 五、组合带关卡分发包

先构建五文件基础目录和独立内容包，再执行：

```powershell
python -m san_tools run compose-editor-distribution `
  derived\editor-release\SanMapEditor `
  dist\content-packs\stage01.sanmap-pack `
  --output dist\SanMapEditor-with-stage01.zip
```

组合命令不会重新解析素材，也不会放宽基础发布审计。输出 ZIP 的顶层仍是五文件基础包，另增加：

```text
content-packs/
  stage01.sanmap-pack
```

因此发布维护者可以分别提供：

- 不带关卡：只发布基础五文件 ZIP；
- 带关卡：发布经过权利确认的组合 ZIP；
- 独立更新关卡：只分发新的 `.sanmap-pack`。
