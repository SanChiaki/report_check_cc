# CheckPage 规则可视化编辑设计

## 背景

当前 CheckPage 只有原始 JSON textarea，用户无法直观地查看和编辑规则配置。RuleConfig.vue 已有完整的规则编辑 UI，但两个页面各自独立实现，RuleConfig 的逻辑无法复用。

## 目标

在 CheckPage 新增可视化规则编辑视图，与 textarea 双向同步，实现 as-you-type 自动校验。

## 架构

### 组件拆分

```
frontend/src/components/
  RuleList.vue      # 规则列表（可复用）
  RuleItem.vue      # 单条规则行（抽取自 RuleConfig.vue）
```

### 双向同步

```
textarea (rulesText)
    │
    │ debounce 300ms after keystroke
    ▼
JSON.parse → rules[]
    │
    │ passed to RuleList as :rules prop
    ▼
RuleList / RuleItem (render + edit)
    │
    │ on rule field change → emit "update:rules"
    ▼
serialize(rules) → rulesText (immediate, no debounce)
```

### 校验流程

```
rulesText 变化
    │
    │ debounce 500ms
    ▼
POST /api/v1/rules/validate
    │
    ├── valid → rulesValid = true, validateErrors = []
    └── invalid → rulesValid = false, validateErrors = [errors]
    │
    │ errors passed to RuleList
    ▼
RuleItem 高亮有问题的规则行（红色边框 + 错误提示）
```

## 组件设计

### RuleItem.vue

从 RuleConfig.vue 抽取的单条规则编辑行，保持完全一致的 UI：
- 折叠/展开状态
- 类型下拉（text, semantic, image, api, external_data, multimodal_check, image_consistency, signature_compare）
- 禁用 toggle
- 动态配置表单（按类型显示对应字段）

新增 props/emits：
- `props: errors: string[]` — 该规则的错误列表，有错误时显示红色边框
- `emit: update:rules` — 字段变更时触发

### RuleList.vue

规则列表容器组件：
- `props: rules: Rule[]`
- `props: errors: Record<string, string[]>` — ruleId → errors 映射
- `emit: update:rules` — 整体规则数组变更
- 复用 RuleConfig 的 `addRule`, `removeRule`, `moveUp`, `moveDown` 逻辑

### CheckPage.vue 改动

1. textarea 保留，下方新增 `<RuleList>` 可视化视图
2. textarea 和 RuleList 通过共享的 `rules` ref 双向绑定
3. 校验错误信息同时显示在 textarea 下方和对应 RuleItem 上
4. 移除原有的手动"验证规则"按钮（已改为自动校验）

### RuleConfig.vue 改动

- 删除 RuleItem 内联实现，改用 `<RuleList>` + `<RuleItem>`
- 删除 `defaultConfig`, `typeLabel`, `addRule`, `removeRule`, `moveUp`, `moveDown` 等重复逻辑

## 防抖策略

| 触发 | 延迟 | 动作 |
|------|------|------|
| textarea 变化 | 300ms | 解析 JSON → 更新 rules[] → 同步 RuleList |
| textarea 变化 | 500ms | 调用 /api/v1/rules/validate |
| RuleList 字段变更 | 0ms（即时） | 序列化 → 回写 rulesText |

## 错误展示

- textarea 下方：保留原有 `error-list` 样式
- RuleItem：当前规则行顶部显示红色错误 banner
- 整体：规则列表顶部显示汇总错误数

## 数据流

```
用户编辑 textarea
    → rulesText 更新
    → debounce 300ms → parse → rules[]
    → RuleList 响应式更新

用户编辑 RuleItem 字段
    → emit update:rules
    → rules[] 更新
    → 立即序列化 → rulesText

校验请求
    → debounce 500ms → validateRules()
    → errors[] 更新
    → textarea 下方 + RuleItem 同步显示错误
```

## 实现步骤

1. 抽取 RuleItem.vue（从 RuleConfig.vue）
2. 创建 RuleList.vue，组合 RuleItem
3. CheckPage.vue 集成：textarea + RuleList 双向绑定 + 自动校验
4. RuleConfig.vue 重构为使用 RuleList
5. 移除 CheckPage 的手动"验证规则"按钮
