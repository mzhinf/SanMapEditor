meta:
  id: stg
  title: 三国霸业 STG scenario stream
  application: 三国霸业 / Emperor.exe
  file-extension: stg
  endian: le
  ks-version: '0.10'
  license: MIT

doc: |
  《三国霸业》.stg 剧本文件的 Kaitai Struct 描述。

  当前结构来自 42 个样本的字节级 roundtrip 验证，覆盖原版 stage00、stage01..stage45，
  以及 SGBY_MAP/new_san 下的非原版大剧本。文件不是早期猜测的固定 76 字节记录表，
  而是 Emperor.exe 风格的对象流：

    u32 present_or_version
    Block root_part1 = u32 payload_size + payload
    Block root_part2 = u32 payload_size + payload
    u32 force_count
    Force * force_count
      Block force_part1
      Block force_part2
      u32 site_list_pre_count_or_flag
      Site * force_part2.body.site_count
        Block site_part1
        Block site_part2
        u32 primary_entity_count
        Entity * primary_entity_count
          Block entity_part1
          Block entity_part2
        optional Entity blocks controlled by site_part2 flags
        site_part2 +0x2AC 固定为保留零值，不作为 Entity 数量解析
    after_forces_tail

  每个 Block 都是 `u32 size + payload[size]`，size 不包含自身 4 字节。
  已见变体：root_part1 0x48/0x4C，force_part2 0x7C/0x84，
  site_part1 0x58/0x5C，entity_part1 0x30/0x34。
  未完全命名的区域按 u32 words 解析和保留，可承载非零值，回写时不得清零。

seq:
  - id: present_or_version
    type: u4
    doc: 文件开头标记/版本。样本多为 1。
  - id: root_part1
    type: root_part1_block
    doc: 剧本标题、年份、剧本编号和剧本模式字段。
  - id: root_part2
    type: root_part2_block
    doc: 剧本级第二块，含势力数镜像和若干模式/状态字段。
  - id: force_count
    type: u4
    doc: 势力数量；EXE 按此值循环读取 Force。
  - id: forces
    type: force
    repeat: expr
    repeat-expr: force_count
    doc: 势力列表。
  - id: after_forces_tail
    type: after_forces_tail
    size-eos: true
    doc: 主势力/据点/实体流结束后的尾区，按 u32 word 保留。

types:
  root_part1_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x48/0x4C。
      - id: body
        type: root_part1_payload
        size: size

  root_part2_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x34。
      - id: body
        type: root_part2_payload
        size: size

  force_part1_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x60。
      - id: body
        type: force_part1_payload
        size: size

  force_part2_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x7C/0x84。
      - id: body
        type: force_part2_payload
        size: size

  site_part1_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x58/0x5C。
      - id: body
        type: site_part1_payload
        size: size

  site_part2_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x2B0。
      - id: body
        type: site_part2_payload
        size: size

  entity_part1_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0x30/0x34。
      - id: body
        type: entity_part1_payload
        size: size

  entity_part2_block:
    seq:
      - id: size
        type: u4
        doc: payload 长度。已见 0xE0。
      - id: body
        type: entity_part2_payload
        size: size

  root_part1_payload:
    doc: root_part1 payload。字段偏移相对于 payload 起点。
    seq:
      - id: scenario_title
        type: str
        size: 16
        encoding: Big5
        terminator: 0
        pad-right: 0
        doc: 剧本名称，Big5 定长 16 字节；长标题可能刚好占满无 0 结尾。
      - id: root1_special_mode_or_title_tail_10
        type: u4
        doc: +0x10 剧本级特殊模式/长标题残留候选；42 样本中 39 个为 0，3 个为非零。
      - id: reserved_zero_14
        type: u4
        doc: +0x14 保留字段；42 样本固定为 0。
      - id: reserved_zero_18
        type: u4
        doc: +0x18 保留字段；42 样本固定为 0。
      - id: scenario_year_start
        type: u4
        doc: 剧本起始年份。
      - id: scenario_year_end
        type: u4
        doc: 剧本结束年份/关卡结束年。
      - id: scenario_mode_flag_a
        type: u4
        doc: 剧本模式标志。普通大剧本常见 1，剧情剧本常见 0。
      - id: reserved_zero_28
        type: u4
        doc: +0x28 保留字段；42 样本固定为 0。
      - id: scenario_mode_flag_b
        type: u4
        doc: 剧本模式标志。普通大剧本常见 1，剧情剧本常见 0。
      - id: scenario_id
        type: u4
        doc: 剧本 ID，通常与 stageNN 编号一致。
      - id: scenario_id_or_duplicate
        type: u4
        doc: 剧本 ID 镜像/子编号。剧情剧本常与 scenario_id 相同。
      - id: root1_variant_38
        type: u4
        doc: +0x38 剧本级变体字段；42 样本中 3 个非零。
      - id: root1_variant_3c
        type: u4
        doc: +0x3C 剧本级变体字段；42 样本中 3 个非零。
      - id: reserved_zero_40
        type: u4
        doc: +0x40 保留字段；42 样本固定为 0。
      - id: root1_scenario_type_44
        type: u4
        doc: +0x44 剧本类型/剧情模式候选；样本值为 0 或 99。
      - id: reserved_zero_48
        type: u4
        if: _io.size >= 0x4c
        doc: +0x48 仅 0x4C payload 版本存在；41 样本固定为 0。

  root_part2_payload:
    doc: root_part2 payload。固定 13 个 u32，偏移相对于 payload 起点。
    seq:
      - id: root2_mode_00
        type: u4
        doc: 剧本级模式/状态字段。
      - id: root2_mode_04
        type: u4
        doc: 剧本级模式/状态字段。
      - id: root2_value_08
        type: u4
        doc: 剧本级数值字段，样本常见 5。
      - id: root2_value_0c
        type: u4
        doc: 剧本级数值字段，样本常见 5。
      - id: root2_pointer_or_mode_10
        type: u4
        doc: +0x10 剧本级指针/模式残留候选；允许非零，回写时原样保留。
      - id: force_count_mirror_candidate
        type: u4
        doc: 势力数量镜像候选；在样本中通常等于顶层 force_count。
      - id: reserved_zero_18
        type: u4
        doc: +0x18 保留字段；42 样本固定为 0。
      - id: root2_mode_1c
        type: u4
        doc: 剧本级模式/状态字段。
      - id: reserved_zero_20
        type: u4
        doc: +0x20 保留字段；42 样本固定为 0。
      - id: root2_pointer_or_mode_24
        type: u4
        doc: +0x24 剧本级指针/模式残留候选；允许非零，回写时原样保留。
      - id: root2_mode_28
        type: u4
        doc: 剧本级模式/状态字段。
      - id: reserved_zero_2c
        type: u4
        doc: +0x2C 保留字段；42 样本固定为 0。
      - id: root2_mode_30
        type: u4
        doc: 剧本级模式/状态字段。

  force:
    doc: 势力对象。Site 数量来自 force_part2.body.site_count。
    seq:
      - id: part1
        type: force_part1_block
        doc: 势力名称和势力基础状态。
      - id: part2
        type: force_part2_block
        doc: 势力 AI/资源/据点列表控制块。
      - id: site_list_pre_count_or_flag
        type: u4
        doc: Site 列表前置 count/flag；样本中通常与 site_count 相同，仍保留原值。
      - id: sites
        type: site
        repeat: expr
        repeat-expr: part2.body.site_count
        doc: 该势力拥有的据点列表。
    instances:
      force_name:
        value: part1.body.force_name
      site_count:
        value: part2.body.site_count

  force_part1_payload:
    doc: force_part1 payload。字段偏移相对于 payload 起点。
    seq:
      - id: force_name
        type: str
        size: 20
        encoding: Big5
        terminator: 0
        pad-right: 0
        doc: 势力名，Big5 定长 20 字节。

      - id: force_slot_or_index_14
        type: u4
        doc: +0x14 势力槽/序号候选；236 样本中 181 个等于父 force 序号，不能视为强一致索引。
      - id: force_lord_person_id
        type: u4
        doc: +0x18 君主/代表武将人物编号候选。
      - id: force_ai_or_diplomacy_mode_1c
        type: u4
        doc: +0x1C 势力 AI/外交模式候选；样本值 0..3。
      - id: force_flag_20
        type: u4
        doc: +0x20 势力标志；样本值 0 或 1。
      - id: force_level_or_group_24
        type: u4
        doc: +0x24 势力等级/分组候选；样本值 0..3。
      - id: force_policy_28
        type: u4
        doc: +0x28 势力策略候选；样本值 0..4。
      - id: force_policy_2c
        type: u4
        doc: +0x2C 势力策略候选；样本值 0..3。
      - id: reserved_zero_30
        type: u4
        doc: +0x30 保留字段；236 样本固定为 0。
      - id: reserved_zero_34
        type: u4
        doc: +0x34 保留字段；236 样本固定为 0。
      - id: force_timer_or_score_38
        type: u4
        doc: +0x38 势力计时/评分候选；允许非零。
      - id: force_timer_or_score_3c
        type: u4
        doc: +0x3C 势力计时/评分候选；允许非零。
      - id: force_flag_40
        type: u4
        doc: +0x40 势力标志；样本值 0、1 或 2。
      - id: reserved_zero_44
        type: u4
        doc: +0x44 保留字段；236 样本固定为 0。
      - id: force_rare_flag_48
        type: u4
        doc: +0x48 稀有势力标志；236 样本仅 1 个非零。
      - id: force_ai_mode_4c
        type: u4
        doc: +0x4C 势力 AI 模式候选；允许非零。
      - id: force_rare_flag_50
        type: u4
        doc: +0x50 稀有势力标志；236 样本仅 1 个非零。
      - id: force_rare_value_54
        type: u4
        doc: +0x54 稀有势力数值；236 样本仅 2 个非零。
      - id: force_budget_or_delay_58
        type: u4
        doc: +0x58 势力预算/延迟候选；常见 0、25、1000、5000。
      - id: force_ai_mode_5c
        type: u4
        doc: +0x5C 势力 AI 模式候选；样本值 0、2、3、4。


  force_part2_payload:
    doc: force_part2 payload。字段偏移相对于 payload 起点。
    seq:
      - id: site_count
        type: u4
        doc: +0x00 该势力拥有的 Site 数量；236 样本恒等于后续 site 列表数量。
      - id: force_index_1based
        type: u4
        doc: +0x04 势力序号镜像；236 样本恒等于父 force 1-based 序号。
      - id: force_lord_person_id_or_ref
        type: u4
        doc: +0x08 君主/势力引用候选。
      - id: reserved_zero_0c
        type: u4
        doc: +0x0C 保留字段；236 样本固定为 0。
      - id: force_runtime_ref_10
        type: u4
        doc: +0x10 运行时引用/指针残留候选；允许非零。
      - id: force_runtime_ref_14
        type: u4
        doc: +0x14 运行时引用/指针残留候选；允许非零。
      - id: reserved_zero_18
        type: u4
        doc: +0x18 保留字段；236 样本固定为 0。
      - id: reserved_zero_1c
        type: u4
        doc: +0x1C 保留字段；236 样本固定为 0。
      - id: reserved_zero_20
        type: u4
        doc: +0x20 保留字段；236 样本固定为 0。
      - id: resource_slots_24_48
        type: u4
        repeat: expr
        repeat-expr: 10
        doc: +0x24..+0x48 资源/外交数值槽；样本通常为 0/20/40/60/80。
      - id: ai_relation_flags_4c_74
        type: u4
        repeat: expr
        repeat-expr: 11
        doc: +0x4C..+0x74 AI/外交关系标志；常见 3 或 0。
      - id: force_strategy_budget_78
        type: u4
        doc: +0x78 势力策略预算/评分候选；常见 0、1000、4600 等。
      - id: reserved_zero_7c
        type: u4
        if: _io.size >= 0x84
        doc: +0x7C 仅 0x84 payload 版本存在；222 样本固定为 0。
      - id: reserved_zero_80
        type: u4
        if: _io.size >= 0x84
        doc: +0x80 仅 0x84 payload 版本存在；222 样本固定为 0。

  site:
    doc: 据点/城市/山寨对象。
    seq:
      - id: part1
        type: site_part1_block
        doc: 与 castle.txt 高度对齐的静态据点数据。
      - id: part2
        type: site_part2_block
        doc: 运行态/AI/可选实体控制数据。
      - id: primary_entity_count
        type: u4
        doc: 主实体列表数量；EXE 按此值读取 Entity。
      - id: entities
        type: entity
        repeat: expr
        repeat-expr: primary_entity_count
        doc: 主实体列表。
      - id: optional_entity_27c
        type: entity
        if: part2.body.optional_entity_flag_27c != 0
        doc: site_part2 +0x27C 非 0 时跟随的可选 Entity。
      - id: optional_entity_280
        type: entity
        if: part2.body.optional_entity_flag_280 != 0
        doc: site_part2 +0x280 非 0 时跟随的可选 Entity。
      - id: optional_entity_284
        type: entity
        if: part2.body.optional_entity_flag_284 != 0
        doc: site_part2 +0x284 非 0 时跟随的可选 Entity。
      - id: optional_entity_288
        type: entity
        if: part2.body.optional_entity_flag_288 != 0
        doc: site_part2 +0x288 非 0 时跟随的可选 Entity。
      - id: optional_entity_28c
        type: entity
        if: part2.body.optional_entity_flag_28c != 0
        doc: site_part2 +0x28C 非 0 时跟随的可选 Entity。
    instances:
      site_name:
        value: part1.body.site_name
      city_index:
        value: part1.body.city_index
      map_x:
        value: part1.body.coord_x
      map_y:
        value: part1.body.coord_y

  site_part1_payload:
    doc: "site_part1 payload。与 castle.txt: 名称 + 数值列 对齐。"
    seq:
      - id: site_name
        type: str
        size: 20
        encoding: Big5
        terminator: 0
        pad-right: 0
        doc: 据点/城市/山寨名。
      - id: city_index
        type: s4
        doc: castle.txt 都市索引。
      - id: house_attr
        type: s4
        doc: castle.txt 房子属性。
      - id: castle_scale
        type: s4
        doc: castle.txt 城规模。
      - id: population
        type: s4
        doc: castle.txt 人口。
      - id: gold
        type: s4
        doc: castle.txt 金。
      - id: food
        type: s4
        doc: castle.txt 粮。
      - id: standby_soldier
        type: s4
        doc: castle.txt 待命士兵。
      - id: develop
        type: s4
        doc: castle.txt 开发值。
      - id: commerce
        type: s4
        doc: castle.txt 商业值。
      - id: security
        type: s4
        doc: castle.txt 治安值。
      - id: develop_limit
        type: s4
        doc: castle.txt 开发上限。
      - id: commerce_limit
        type: s4
        doc: castle.txt 商业上限。
      - id: security_limit
        type: s4
        doc: castle.txt 治安上限。
      - id: coord_x
        type: s4
        doc: castle.txt 座标X。
      - id: coord_y
        type: s4
        doc: castle.txt 座标Y。
      - id: governor
        type: s4
        doc: castle.txt 太守。
      - id: general_count_or_slot
        type: s4
        doc: castle.txt 武将。
      - id: site_part1_extra_words
        type: u4_words
        size-eos: true
        doc: 0x5C 版本比 0x58 版本多出的尾部 u32 字段；按原值保留。


  site_part2_payload:
    doc: site_part2 payload。运行态 AI/可选实体控制区。+0x27C..+0x28C 是五个可选 Entity flag；+0x2AC 在 1043 个据点样本中固定为 0，不是额外 Entity 数量。
    seq:
      - id: reserved_zero_000
        type: u4
        doc: +0x000 保留字段；1043 样本固定为 0。
      - id: runtime_coord_or_spawn_x_004
        type: s4
        doc: +0x004 运行时坐标/生成点 X 候选；不等于 castle.txt 坐标 X。
      - id: runtime_coord_or_spawn_y_008
        type: s4
        doc: +0x008 运行时坐标/生成点 Y 候选；不等于 castle.txt 坐标 Y。
      - id: site_kind_or_force_group_00c
        type: u4
        doc: +0x00C 据点类别/势力组候选；样本值 1..10。
      - id: site_serial_010
        type: u4
        doc: +0x010 据点序号候选；样本值 1..99。
      - id: site_flag_014
        type: u4
        doc: +0x014 稀有标志；样本值 0 或 1。
      - id: reserved_zero_018
        type: u4
        doc: +0x018 保留字段；1043 样本固定为 0。
      - id: site_small_counter_01c
        type: u4
        doc: +0x01C 据点小计数/等级候选；样本值 0..16。
      - id: reserved_zero_020
        type: u4
        doc: +0x020 保留字段；1043 样本固定为 0。
      - id: sentinel_minus_one_024
        type: u4
        doc: +0x024 固定哨兵值 0xFFFFFFFF；1043 样本恒定。
      - id: reserved_zero_028
        type: u4
        doc: +0x028 保留字段；1043 样本固定为 0。
      - id: reserved_zero_02c
        type: u4
        doc: +0x02C 保留字段；1043 样本固定为 0。
      - id: site_flag_030
        type: u4
        doc: +0x030 稀有标志；样本值 0 或 1。
      - id: reserved_zero_034
        type: u4
        doc: +0x034 保留字段；1043 样本固定为 0。
      - id: reserved_zero_038
        type: u4
        doc: +0x038 保留字段；1043 样本固定为 0。
      - id: site_flag_03c
        type: u4
        doc: +0x03C 稀有标志；样本值 0 或 1。
      - id: reserved_zero_040_054
        type: u4
        repeat: expr
        repeat-expr: 6
        doc: +0x040..+0x054 保留字段；1043 样本全部为 0。
      - id: ai_template_params_058_130
        type: u4
        repeat: expr
        repeat-expr: 55
        doc: +0x058..+0x130 AI/行动模板参数表；包含 5/6、40、20、4、50、100 等固定或低基数参数。
      - id: reserved_zero_134_20c
        type: u4
        repeat: expr
        repeat-expr: 55
        doc: +0x134..+0x20C 保留带；1043 样本全部为 0。
      - id: runtime_tail_words_210_278
        type: u4
        repeat: expr
        repeat-expr: 27
        doc: +0x210..+0x278 运行时引用/脚本/浮点位型/状态尾字段；允许非零，回写时必须保留。
      - id: optional_entity_flag_27c
        type: u4
        doc: +0x27C 非 0 时 site 后跟随一个可选 Entity；1043 样本中 19 个为 1。
      - id: optional_entity_flag_280
        type: u4
        doc: +0x280 非 0 时 site 后跟随一个可选 Entity；1043 样本中 1 个为 1。
      - id: optional_entity_flag_284
        type: u4
        doc: +0x284 非 0 时 site 后跟随一个可选 Entity；当前样本固定为 0，EXE 有对应槽位。
      - id: optional_entity_flag_288
        type: u4
        doc: +0x288 非 0 时 site 后跟随一个可选 Entity；1043 样本中 1 个为 1。
      - id: optional_entity_flag_28c
        type: u4
        doc: +0x28C 非 0 时 site 后跟随一个可选 Entity；1043 样本中 1 个为 1。
      - id: reserved_zero_290
        type: u4
        doc: +0x290 保留字段；1043 样本固定为 0。
      - id: runtime_rare_flag_294
        type: u4
        doc: +0x294 稀有标志；1043 样本中 2 个为 1。
      - id: runtime_budget_298
        type: u4
        doc: +0x298 运行时预算/延迟候选；常见 0、100、200、300。
      - id: runtime_bitfield_29c
        type: u4
        doc: +0x29C 运行时位域候选；常见 0 或 65536。
      - id: runtime_mode_2a0
        type: u4
        doc: +0x2A0 运行时模式候选；常见 0 或 1。
      - id: reserved_zero_2a4
        type: u4
        doc: +0x2A4 保留字段；1043 样本固定为 0。
      - id: reserved_zero_2a8
        type: u4
        doc: +0x2A8 保留字段；1043 样本固定为 0。
      - id: reserved_zero_2ac
        type: u4
        doc: +0x2AC 保留字段；1043 样本固定为 0。它不是额外 Entity 数量。

  entity:
    doc: 实体对象。通常代表武将、普通士兵、盗贼或剧情单位。
    seq:
      - id: part1
        type: entity_part1_block
        doc: 运行态字段。
      - id: part2
        type: entity_part2_block
        doc: 与 general.txt 高度对齐的静态/能力字段。
    instances:
      entity_name:
        value: part2.body.entity_name
      person_id:
        value: part2.body.person_id
      troop_count:
        value: part2.body.troop_count


  entity_part1_payload:
    doc: entity_part1 payload。运行时状态字段；已见 0x30 或 0x34 版本。+0x00..+0x20 在 4472 个实体样本中全部为 0，不是所属势力。
    seq:
      - id: reserved_zero_00_20
        type: u4
        repeat: expr
        repeat-expr: 9
        doc: +0x00..+0x20 保留/填充字段；4472 个实体样本全部为 0。
      - id: runtime_value_24
        type: u4
        doc: +0x24 运行时状态值；4472 样本中 87 个非零，常见 260、30、110 等。
      - id: runtime_ref_28
        type: u4
        doc: +0x28 运行时引用/位域候选；4472 样本中 5 个非零。
      - id: runtime_float_or_state_2c
        type: u4
        doc: +0x2C 运行时浮点位型/状态候选；常见 0、0x3F800000、0x3F19999A、0xFFFF。
      - id: runtime_force_or_ai_side_30
        type: u4
        if: _io.size >= 0x34
        doc: +0x30 仅 0x34 payload 版本存在；运行时势力/AI 阵营候选，约 74.6% 样本等于父 Force 序号，不能写死为 owner。

  entity_part2_payload:
    doc: "entity_part2 payload。与 general.txt: 名称 + 数值列 对齐。"
    seq:
      - id: entity_name
        type: str
        size: 20
        encoding: Big5
        terminator: 0
        pad-right: 0
        doc: 武将/兵种模板名。
      - id: person_id
        type: s4
        doc: general.txt 人物编号。
      - id: portrait_id
        type: s4
        doc: general.txt 头像编号。
      - id: static_owner_id
        type: s4
        doc: general.txt 所属君主；运行时归属需结合父 Force、父 Site 和 entity_part1 的运行时阵营候选判断。
      - id: static_location_id
        type: s4
        doc: general.txt 所在地；运行时位置优先看父 Site。
      - id: command
        type: s4
        doc: general.txt 统御力。
      - id: soldier_type_id
        type: s4
        doc: general.txt 兵种号；可关联 soldier.txt 人物编号。
      - id: level
        type: s4
        doc: general.txt 等级。
      - id: troop_count
        type: s4
        doc: general.txt 带兵数。
      - id: martial_force
        type: s4
        doc: general.txt 武力。
      - id: intellect
        type: s4
        doc: general.txt 智力。
      - id: loyalty
        type: s4
        doc: general.txt 忠诚值。
      - id: experience
        type: s4
        doc: general.txt 经验值。
      - id: skill_fire_1
        type: s4
        doc: general.txt 火花技1。
      - id: skill_fire_2
        type: s4
        doc: general.txt 火炎技2。
      - id: skill_fire_3
        type: s4
        doc: general.txt 火龙技3。
      - id: skill_stone_1
        type: s4
        doc: general.txt 落石技1。
      - id: skill_stone_2
        type: s4
        doc: general.txt 崩石技2。
      - id: skill_stone_3
        type: s4
        doc: general.txt 陨石技3。
      - id: skill_thunder_1
        type: s4
        doc: general.txt 落雷技1。
      - id: skill_thunder_2
        type: s4
        doc: general.txt 狂雷技2。
      - id: skill_thunder_3
        type: s4
        doc: general.txt 爆雷技3。
      - id: skill_slash_1
        type: s4
        doc: general.txt 一气斩1。
      - id: skill_slash_2
        type: s4
        doc: general.txt 月气斩2。
      - id: skill_slash_3
        type: s4
        doc: general.txt 爆发斩3。
      - id: skill_spear_1
        type: s4
        doc: general.txt 枪1。
      - id: skill_spear_2
        type: s4
        doc: general.txt 枪2。
      - id: skill_spear_3
        type: s4
        doc: general.txt 枪3。
      - id: skill_arrow_1
        type: s4
        doc: general.txt 穿心箭技1。
      - id: skill_arrow_2
        type: s4
        doc: general.txt 乱矢箭2。
      - id: skill_arrow_3
        type: s4
        doc: general.txt 万箭技3。
      - id: skill_persuade
        type: s4
        doc: general.txt 说服技。
      - id: skill_inspire
        type: s4
        doc: general.txt 鼓舞技。
      - id: skill_shout
        type: s4
        doc: general.txt 大喝技。
      - id: skill_confuse
        type: s4
        doc: general.txt 迷惑技。
      - id: special_skill
        type: s4
        doc: general.txt 必杀技。
      - id: action_state
        type: s4
        doc: general.txt 行动状态。
      - id: imprisoned_flag
        type: s4
        doc: general.txt 被关=1。
      - id: loaded_flag
        type: s4
        doc: general.txt 读取=1。
      - id: attribute
        type: s4
        doc: general.txt 属性。
      - id: self_ref
        type: s4
        doc: general.txt 参照自己。
      - id: alert_ai
        type: s4
        doc: general.txt 武将警戒。
      - id: chase_ai
        type: s4
        doc: general.txt 武将追捕。
      - id: retreat_ai
        type: s4
        doc: general.txt 武将撤退。
      - id: action_policy
        type: s4
        doc: general.txt 行动方针。
      - id: ambush_field
        type: s4
        doc: general.txt 伏兵=?。
      - id: betrayal_force_id
        type: s4
        doc: general.txt 叛变国id。
      - id: max_troop_count
        type: s4
        doc: general.txt 最大带兵数。
      - id: max_martial_force
        type: s4
        doc: general.txt 最大武力。
      - id: max_intellect
        type: s4
        doc: general.txt 最大智力。
      - id: reserved_d8
        type: s4
        doc: general.txt 未覆盖的尾部字段，常为 0，但回写时应保留。
      - id: reserved_dc
        type: s4
        doc: general.txt 未覆盖的尾部字段，常为 0，但回写时应保留。

  after_forces_tail:
    doc: 主对象流后的尾区。尾区长度可小于、等于或大于 0xA0。
    seq:
      - id: middle_tail_words
        type: u4_words
        size: _io.size - 0xa0
        if: _io.size > 0xa0
        doc: 大于 0xA0 的前置尾区，按 u32 word 保留。大剧本中可检测到 entity-like 片段，但列表规则尚未完全收口。
      - id: trailer_or_small_tail_words
        type: u4_words
        size: "_io.size > 0xa0 ? 0xa0 : _io.size"
        doc: 最后 0xA0 字节候选尾块；若整个尾区小于 0xA0，则保存全部尾区。
    instances:
      middle_tail_size:
        value: "_io.size > 0xa0 ? _io.size - 0xa0 : 0"
        doc: 前置尾区字节数。
      trailer_or_small_tail_size:
        value: "_io.size > 0xa0 ? 0xa0 : _io.size"
        doc: 尾块字节数。

  u4_words:
    doc: 未命名但按 4 字节对齐的保留/状态区。允许非零值，回写时必须保留。
    seq:
      - id: words
        type: u4
        repeat: eos
