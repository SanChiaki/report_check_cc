<template>
  <div class="rule-list">
    <div v-if="rules.length === 0" class="empty-state">
      <p>暂无规则，点击「新增规则」开始配置</p>
    </div>

    <RuleItem
      v-for="(rule, idx) in rules"
      :key="rule.id"
      :rule="rule"
      :index="idx"
      :errors="errorsByRuleId[rule.id] || []"
      :ref="(el) => setItemRef(el, idx)"
      @update:rule="(updated: Rule) => onRuleUpdate(idx, updated)"
    >
      <template #actions>
        <button class="icon-btn" @click.stop="moveUp(idx)" :disabled="idx === 0" title="上移">↑</button>
        <button class="icon-btn" @click.stop="moveDown(idx)" :disabled="idx === rules.length - 1" title="下移">↓</button>
        <button class="icon-btn danger" @click.stop="removeRule(idx)" title="删除">✕</button>
      </template>
    </RuleItem>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import RuleItem from './RuleItem.vue'

interface Rule {
  id: string
  name: string
  type: string
  disabled: boolean
  config: Record<string, unknown>
}

const props = defineProps<{
  rules: Rule[]
  errors?: Array<{ rule_id: string; field: string; message: string }>
}>()

const emit = defineEmits<{
  'update:rules': [rules: Rule[]]
}>()

// Map backend errors {rule_id, field, message} to errors per rule id
const errorsByRuleId = ref<Record<string, string[]>>({})

watch(
  () => props.errors,
  (errs) => {
    const map: Record<string, string[]> = {}
    for (const e of errs ?? []) {
      if (!map[e.rule_id]) map[e.rule_id] = []
      map[e.rule_id].push(e.message)
    }
    errorsByRuleId.value = map
  },
  { immediate: true },
)

function defaultConfig(type: string): Record<string, unknown> {
  if (type === 'text') return { keywords: [], match_mode: 'any', case_sensitive: false }
  if (type === 'semantic') return { requirement: '' }
  if (type === 'image') return { requirement: '', nearby_keywords: [] }
  if (type === 'api') return { extract_description: '', api_url: '', method: 'POST' }
  if (type === 'external_data') return { extract_description: '', data_url: '', analysis_requirement: '' }
  if (type === 'multimodal_check') return { requirement: '', context_hint: '' }
  if (type === 'image_consistency') return { requirement: '检查项的配图是否符合检查项的描述', strict_mode: false }
  if (type === 'signature_compare') return { file1_ref: 0, file2_ref: 1, signature_description: '客户手写签名', grid_size: 20, padding_cells: 1, context_hint: '' }
  return {}
}

function onRuleUpdate(idx: number, updatedRule: Rule) {
  const updated = [...props.rules]
  updated[idx] = updatedRule
  emit('update:rules', updated)
}

function addRule() {
  const idx = props.rules.length + 1
  const newRule: Rule = {
    id: `r${idx}`,
    name: '',
    type: 'text',
    disabled: false,
    config: defaultConfig('text'),
  }
  emit('update:rules', [...props.rules, newRule])
}

function removeRule(idx: number) {
  const updated = [...props.rules]
  updated.splice(idx, 1)
  emit('update:rules', updated)
}

function moveUp(idx: number) {
  if (idx === 0) return
  const updated = [...props.rules]
  ;[updated[idx - 1], updated[idx]] = [updated[idx], updated[idx - 1]]
  emit('update:rules', updated)
}

function moveDown(idx: number) {
  if (idx === props.rules.length - 1) return
  const updated = [...props.rules]
  ;[updated[idx], updated[idx + 1]] = [updated[idx + 1], updated[idx]]
  emit('update:rules', updated)
}

// Refs to RuleItem instances for calling emitUpdate
const itemRefs = ref<Record<number, { localRule: Rule; emitUpdate: () => void } | null>>({})

function setItemRef(el: unknown, idx: number) {
  itemRefs.value[idx] = el as (typeof itemRefs.value)[number]
}

defineExpose({
  addRule,
  removeRule,
  moveUp,
  moveDown,
})
</script>

<style scoped>
.rule-list { display: flex; flex-direction: column; gap: 8px; }

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 14px;
}

.icon-btn {
  background: none;
  border: 1px solid #e0e6ed;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 13px;
  color: #666;
  transition: background 0.15s, color 0.15s;
}

.icon-btn:hover:not(:disabled) { background: #f0f3ff; color: #4f6ef7; border-color: #4f6ef7; }
.icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.icon-btn.danger:hover:not(:disabled) { background: #fff5f5; color: #e53e3e; border-color: #e53e3e; }
</style>
