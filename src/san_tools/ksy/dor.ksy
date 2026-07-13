meta:
  id: dor
  file-extension: dor
  endian: le

seq:
  - id: magic_bytes
    contents: [0x44, 0x6f, 0x6f, 0x72, 0x20, 0x20, 0x20, 0x20, 0x44, 0x61, 0x74, 0x61]
    doc: "魔术字：Door    Data"

  - id: record_size
    type: u4
    doc: "记录长度，u32 字段数量(通常为 15)"

  - id: dor_groups
    type: dor_group
    repeat: eos
    doc: "城门分组，重复直到文件结束"

types:
  dor_group:
    seq:
      - id: record_count
        type: u4
        doc: "本组城门记录数量"

      - id: records
        type: dor_record
        repeat: expr
        repeat-expr: record_count
        doc: "城门记录数组"

  dor_record:
    seq:
      - id: door_x
        type: u4
        doc: "城门 X 轴坐标，字节偏移 +0x00"

      - id: door_y
        type: u4
        doc: "城门 Y 轴坐标，字节偏移 +0x04"

      - id: door_ori
        type: u4
        doc: "城门朝向，0 表示朝右，1 表示朝左，字节偏移 +0x08"

      - id: reserved0
        type: u4
        repeat: expr
        repeat-expr: 9
        doc: "连续 9 个填充/保留 u32，字节偏移 +0x0C ~ +0x2C"

      - id: site_x
        type: u4
        doc: "城池 X 轴坐标，字节偏移 +0x30"

      - id: site_y
        type: u4
        doc: "城池 Y 轴坐标，字节偏移 +0x34"

      - id: reserved1
        type: u4
        doc: "填充/保留 u32，字节偏移 +0x38"

instances:
  record_size_bytes:
    value: record_size * 4
    doc: "单条记录字节数，通常为 15 * 4 = 60 字节"
