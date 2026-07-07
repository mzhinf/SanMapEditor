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
        extra Entity blocks controlled by site_part2 +0x2AC
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
      - id: root1_unknown_10
        type: u4
        doc: 剧本级保留/模式字段。普通大剧本常见 0x4000。
      - id: root1_unknown_14
        type: u4
        doc: 剧本级保留字段。
      - id: root1_unknown_18
        type: u4
        doc: 剧本级保留字段。
      - id: scenario_year_start
        type: u4
        doc: 剧本起始年份。
      - id: scenario_year_end
        type: u4
        doc: 剧本结束年份/关卡结束年。
      - id: scenario_mode_flag_a
        type: u4
        doc: 剧本模式标志。普通大剧本常见 1，剧情剧本常见 0。
      - id: root1_unknown_28
        type: u4
        doc: 剧本级保留字段。
      - id: scenario_mode_flag_b
        type: u4
        doc: 剧本模式标志。普通大剧本常见 1，剧情剧本常见 0。
      - id: scenario_id
        type: u4
        doc: 剧本 ID，通常与 stageNN 编号一致。
      - id: scenario_id_or_duplicate
        type: u4
        doc: 剧本 ID 镜像/子编号。剧情剧本常与 scenario_id 相同。
      - id: root1_unknown_38
        type: u4
        doc: 剧本级保留字段；stage00 等样本可为非零。
      - id: root1_unknown_3c
        type: u4
        doc: 剧本级保留字段；stage00 等样本可为非零。
      - id: root1_unknown_40
        type: u4
        doc: 剧本级保留字段。
      - id: root1_unknown_44
        type: u4
        doc: 剧本级保留字段；部分剧情剧本常见 99。
      - id: root1_unknown_48
        type: u4
        if: _io.size >= 0x4c
        doc: 仅 0x4C payload 版本存在的尾部保留字段。

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
      - id: root2_unknown_10
        type: u4
        doc: 剧本级保留字段，可为非零。
      - id: force_count_mirror_candidate
        type: u4
        doc: 势力数量镜像候选；在样本中通常等于顶层 force_count。
      - id: root2_unknown_18
        type: u4
        doc: 剧本级保留字段。
      - id: root2_mode_1c
        type: u4
        doc: 剧本级模式/状态字段。
      - id: root2_unknown_20
        type: u4
        doc: 剧本级保留字段。
      - id: root2_unknown_24
        type: u4
        doc: 剧本级保留字段，可为非零。
      - id: root2_mode_28
        type: u4
        doc: 剧本级模式/状态字段。
      - id: root2_unknown_2c
        type: u4
        doc: 剧本级保留字段。
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
      - id: force_index_1based
        type: u4
        doc: 势力序号候选，1-based；多数普通剧本与列表顺序一致。
      - id: force_lord_person_id
        type: u4
        doc: 君主/代表武将人物编号候选；可与 general.txt 关联。
      - id: force_part1_words_after_lord
        type: u4_words
        size-eos: true
        doc: 势力基础状态余下 u32 字段。可为非零，回写时应保留。

  force_part2_payload:
    doc: force_part2 payload。字段偏移相对于 payload 起点。
    seq:
      - id: site_count
        type: u4
        doc: 该势力拥有的 Site 数量；EXE 按此值循环读取 Site。
      - id: force_index_1based
        type: u4
        doc: 势力序号镜像候选，1-based。
      - id: force_lord_person_id_or_ref
        type: u4
        doc: 君主/势力引用候选。
      - id: force_part2_words_after_header
        type: u4_words
        size-eos: true
        doc: 势力 AI、资源、外交或策略状态余下 u32 字段。0x7C/0x84 版本长度不同。

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
      - id: extra_entities_2ac
        type: entity
        repeat: expr
        repeat-expr: part2.body.extra_entity_count_candidate_2ac
        if: part2.body.extra_entity_count_candidate_2ac != 0
        doc: site_part2 +0x2AC 控制的额外 Entity 候选列表；样本中下一块符合 Entity 形态时成立。
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
    doc: site_part2 payload。运行态/AI/可选实体控制区。
    seq:
      - id: runtime_00
        type: u4
        doc: 未命名运行态字段。
      - id: runtime_x_or_state_04
        type: s4
        doc: 运行态坐标/状态候选；不是 castle.txt 座标X。
      - id: runtime_y_or_state_08
        type: s4
        doc: 运行态坐标/状态候选；不是 castle.txt 座标Y。
      - id: runtime_words_0c_27b
        type: u4
        repeat: expr
        repeat-expr: 0x9c
        doc: site_part2 +0x0C..+0x27B 的运行态/AI 保留 u32 字段。
      - id: optional_entity_flag_27c
        type: u4
        doc: 非 0 时，site 后跟随一个可选 Entity。
      - id: optional_entity_flag_280
        type: u4
        doc: 非 0 时，site 后跟随一个可选 Entity。
      - id: optional_entity_flag_284
        type: u4
        doc: 非 0 时，site 后跟随一个可选 Entity。
      - id: optional_entity_flag_288
        type: u4
        doc: 非 0 时，site 后跟随一个可选 Entity。
      - id: optional_entity_flag_28c
        type: u4
        doc: 非 0 时，site 后跟随一个可选 Entity。
      - id: runtime_words_290_2ab
        type: u4
        repeat: expr
        repeat-expr: 7
        doc: site_part2 +0x290..+0x2AB 的运行态/AI 保留 u32 字段。
      - id: extra_entity_count_candidate_2ac
        type: u4
        doc: 额外 Entity 数量候选；样本中下一块符合 Entity 形态时成立。

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
      owner_force_index_runtime:
        value: part1.body.owner_force_index_runtime

  entity_part1_payload:
    doc: entity_part1 payload。运行态/位置/状态字段；已见 0x30 或 0x34 版本。
    seq:
      - id: owner_force_index_runtime
        type: u4
        doc: 运行时所属势力序号候选，通常与父 Force 一致。
      - id: runtime_04
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_08
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_0c
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_10
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_14
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_18
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_1c
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_20
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_24
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_28
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_2c
        type: s4
        doc: 运行态/位置/状态字段。
      - id: runtime_30
        type: s4
        if: _io.size >= 0x34
        doc: 仅 0x34 payload 版本存在的运行态/位置/状态字段。

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
        doc: general.txt 所属君主；运行时归属优先看 entity_part1.owner_force_index_runtime 和父 Force。
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
      - id: ambush_unknown
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
