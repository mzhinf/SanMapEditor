meta:
  id: m
  file-extension: m
  endian: le

seq:
  - id: width
    type: u4
    doc: "地图 X 轴长度"

  - id: height
    type: u4
    doc: "地图 Y 轴长度"

  - id: magic_bytes
    contents: [0x48, 0x65, 0x6c, 0x6c, 0x6f, 0x31, 0x2e, 0x30]
    doc: "魔术字：Hello1.0"

  - id: cells
    type: map_cell
    repeat: expr
    repeat-expr: width * height
    doc: "地图格子记录数组"

types:
  map_cell:
    seq:
      - id: acwx
        type: s2
        doc: "基础地形 tile 索引"

      - id: acwy
        type: s2
        doc: "叠加/过渡 tile 索引，-1 表示空层"

      - id: acwz
        type: s2
        doc: "建筑/物件 tile 索引，-1 表示空层"

      - id: reserved0
        contents: [0x00, 0x00]
        doc: "填充 0"

      - id: terrain_tag
        type: u1
        doc: "地形标记"

      - id: blocked
        type: u1
        doc: "可通行标记"

      - id: site_trigger
        type: u1
        doc: "据点势力范围"

      - id: site_area
        type: u1
        doc: "据点核心区域"

      - id: reserved1
        contents: [0x00]
        doc: "填充 0"

      - id: minimap_color
        type: u1
        doc: "小地图渲染颜色索引"

      - id: reserved2
        contents: [0x00, 0x00]
        doc: "填充 0"

instances:
  cell_size:
    value: width * height
    doc: "地图单元格数，通常为 width * height"
