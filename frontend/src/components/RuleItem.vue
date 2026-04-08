<template>
  <div class="rule-row" :class="{ expanded }">
    <!-- Error banner -->
    <div v-if="(errors ?? []).length > 0" class="error-banner">
      <p v-for="(err, i) in (errors ?? [])" :key="i">⚠ {{ err }}</p>
    </div>

    <!-- Header -->
    <div class="rule-row-header" @click="toggle">
      <div class="rule-row-left">
        <span class="rule-index">#{{ index + 1 }}</span>
        <span class="rule-name-text">{{ rule.name || '(未命名)' }}</span>
        <span class="type-badge">{{ typeLabel(rule.type) }}</span>
        <span v-if="rule.disabled" class="disabled-badge">已禁用</span>
      </div>
      <div class="rule-row-actions">
        <slot name="actions" />
        <span class="expand-icon">{{ expanded ? '▲' : '▼' }}</span>
      </div>
    </div>

    <!-- Form -->
    <div v-if="expanded" class="rule-form">
      <div class="form-grid">
        <div class="form-field">
          <label>规则 ID</label>
          <input v-model="localRule.id" type="text" class="form-input" placeholder="唯一标识，如 r1" />
        </div>
        <div class="form-field">
          <label>规则名称</label>
          <input v-model="localRule.name" type="text" class="form-input" placeholder="如：检查交付内容" />
        </div>
        <div class="form-field">
          <label>规则类型</label>
          <select v-model="localRule.type" class="form-input" @change="onTypeChange">
            <option value="text">文本检查</option>
            <option value="semantic">语义检查</option>
            <option value="image">图片检查</option>
            <option value="api">API 检查</option>
            <option value="external_data">外部数据检查</option>
            <option value="multimodal_check">多模态检查</option>
            <option value="image_consistency">配图一致性检查</option>
            <option value="signature_compare">签名对比检查</option>
          </select>
        </div>
        <div class="form-field">
          <label>禁用</label>
          <label class="toggle">
            <input type="checkbox" v-model="localRule.disabled" />
            <span class="toggle-slider" />
          </label>
        </div>
      </div>

      <!-- Text config -->
      <template v-if="localRule.type === 'text'">
        <div class="config-section">
          <h3 class="config-title">文本检查配置</h3>
          <div class="form-field">
            <label>关键词（每行一个）</label>
            <textarea
              :value="(localRule.config.keywords || []).join('\n')"
              @input="localRule.config.keywords = ($event.target as HTMLTextAreaElement).value.split('\n').filter(Boolean)"
              class="form-input textarea-sm"
              placeholder="交付内容&#10;验收报告"
            />
          </div>
          <div class="form-row-inline">
            <div class="form-field">
              <label>匹配模式</label>
              <select v-model="localRule.config.match_mode" class="form-input">
                <option value="any">任意匹配 (any)</option>
                <option value="all">全部匹配 (all)</option>
                <option value="exact">精确匹配 (exact)</option>
              </select>
            </div>
            <div class="form-field">
              <label>区分大小写</label>
              <label class="toggle">
                <input type="checkbox" v-model="localRule.config.case_sensitive" />
                <span class="toggle-slider" />
              </label>
            </div>
          </div>
        </div>
      </template>

      <!-- Semantic config -->
      <template v-else-if="localRule.type === 'semantic'">
        <div class="config-section">
          <h3 class="config-title">语义检查配置</h3>
          <div class="form-field">
            <label>检查要求描述</label>
            <textarea
              v-model="localRule.config.requirement"
              class="form-input textarea-sm"
              placeholder="移交记录中要包含移交人、移交时间、移交命令"
            />
          </div>
        </div>
      </template>

      <!-- Image config -->
      <template v-else-if="localRule.type === 'image'">
        <div class="config-section">
          <h3 class="config-title">图片检查配置</h3>
          <div class="form-field">
            <label>图片内容要求</label>
            <textarea
              v-model="localRule.config.requirement"
              class="form-input textarea-sm"
              placeholder="清理机房，图片应显示干净整洁的机房环境"
            />
          </div>
          <div class="form-field">
            <label>关键词过滤（附近文字，每行一个）</label>
            <textarea
              :value="(localRule.config.nearby_keywords || []).join('\n')"
              @input="localRule.config.nearby_keywords = ($event.target as HTMLTextAreaElement).value.split('\n').filter(Boolean)"
              class="form-input textarea-sm"
              placeholder="机房&#10;清理"
            />
          </div>
        </div>
      </template>

      <!-- API config -->
      <template v-else-if="localRule.type === 'api'">
        <div class="config-section">
          <h3 class="config-title">API 检查配置</h3>
          <div class="form-field">
            <label>提取内容描述</label>
            <input v-model="localRule.config.extract_description" type="text" class="form-input" placeholder="报告中的客户邮箱地址" />
          </div>
          <div class="form-field">
            <label>API URL</label>
            <input v-model="localRule.config.api_url" type="text" class="form-input" placeholder="https://api.example.com/validate" />
          </div>
          <div class="form-field">
            <label>请求方法</label>
            <select v-model="localRule.config.method" class="form-input">
              <option value="GET">GET</option>
              <option value="POST">POST</option>
            </select>
          </div>
        </div>
      </template>

      <!-- External data config -->
      <template v-else-if="localRule.type === 'external_data'">
        <div class="config-section">
          <h3 class="config-title">外部数据检查配置</h3>
          <div class="form-field">
            <label>提取内容描述</label>
            <input v-model="localRule.config.extract_description" type="text" class="form-input" placeholder="报告中的设备列表" />
          </div>
          <div class="form-field">
            <label>外部数据 API URL</label>
            <input v-model="localRule.config.data_url" type="text" class="form-input" placeholder="https://api.example.com/devices" />
          </div>
          <div class="form-field">
            <label>分析要求</label>
            <textarea
              v-model="localRule.config.analysis_requirement"
              class="form-input textarea-sm"
              placeholder="报告中的设备是否全部包含在设备清单中"
            />
          </div>
        </div>
      </template>

      <!-- Multimodal check config -->
      <template v-else-if="localRule.type === 'multimodal_check'">
        <div class="config-section">
          <h3 class="config-title">多模态检查配置</h3>
          <div class="form-field">
            <label>检查要求</label>
            <textarea
              v-model="localRule.config.requirement"
              class="form-input textarea-sm"
              placeholder="检查报告中的每个质检项是否都有对应的现场照片证明"
            />
          </div>
          <div class="form-field">
            <label>上下文提示（可选）</label>
            <input v-model="localRule.config.context_hint" type="text" class="form-input" placeholder="质检项通常在'质检分类'下方列出" />
          </div>
        </div>
      </template>

      <!-- Image consistency config -->
      <template v-else-if="localRule.type === 'image_consistency'">
        <div class="config-section">
          <h3 class="config-title">配图一致性检查配置</h3>
          <div class="form-field">
            <label>检查要求</label>
            <textarea
              v-model="localRule.config.requirement"
              class="form-input textarea-sm"
              placeholder="检查项的配图是否符合检查项的描述"
            />
          </div>
          <div class="form-field">
            <label>严格模式</label>
            <label class="toggle">
              <input type="checkbox" v-model="localRule.config.strict_mode" />
              <span class="toggle-slider" />
            </label>
          </div>
        </div>
      </template>

      <!-- Signature compare config -->
      <template v-else-if="localRule.type === 'signature_compare'">
        <div class="config-section">
          <h3 class="config-title">签名对比检查配置</h3>
          <div class="form-field">
            <label>签名描述</label>
            <input v-model="localRule.config.signature_description" type="text" class="form-input" placeholder="客户手写签名" />
          </div>
          <div class="form-row-inline">
            <div class="form-field">
              <label>文件 1 索引</label>
              <input v-model.number="localRule.config.file1_ref" type="number" class="form-input" placeholder="0（主文件）" min="0" />
            </div>
            <div class="form-field">
              <label>文件 2 索引</label>
              <input v-model.number="localRule.config.file2_ref" type="number" class="form-input" placeholder="1（附加文件）" min="0" />
            </div>
          </div>
          <div class="form-row-inline">
            <div class="form-field">
              <label>网格大小</label>
              <input v-model.number="localRule.config.grid_size" type="number" class="form-input" placeholder="20" min="10" max="30" />
            </div>
            <div class="form-field">
              <label>边界扩展格子数</label>
              <input v-model.number="localRule.config.padding_cells" type="number" class="form-input" placeholder="1" min="0" max="3" />
            </div>
          </div>
          <div class="form-field">
            <label>上下文提示（可选）</label>
            <input v-model="localRule.config.context_hint" type="text" class="form-input" placeholder="签名通常在报告末尾的签字栏" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

interface RuleConfig {
  keywords?: string[]
  match_mode?: string
  case_sensitive?: boolean
  requirement?: string
  nearby_keywords?: string[]
  extract_description?: string
  api_url?: string
  method?: string
  data_url?: string
  analysis_requirement?: string
  signature_description?: string
  file1_ref?: number
  file2_ref?: number
  grid_size?: number
  padding_cells?: number
  strict_mode?: boolean
  context_hint?: string
  [key: string]: unknown
}

interface Rule {
  id: string
  name: string
  type: string
  disabled: boolean
  config: RuleConfig
}

const props = defineProps<{
  rule: Rule
  index: number
  errors?: string[]
}>()

const emit = defineEmits<{
  'update:rule': [rule: Rule]
}>()

const expanded = ref(false)

// Local copy to edit without emitting on every keystroke
const localRule = ref<Rule>(JSON.parse(JSON.stringify(props.rule)))

// Sync from parent when parent updates the rule (e.g. from textarea)
watch(
  () => props.rule,
  (newRule) => {
    localRule.value = JSON.parse(JSON.stringify(newRule))
  },
  { deep: true },
)

// Emit on blur/change for text inputs, and immediately for selects/toggles
function emitUpdate() {
  const updated: Rule = JSON.parse(JSON.stringify(localRule.value))
  emit('update:rule', updated)
}

function onTypeChange() {
  localRule.value.config = defaultConfig(localRule.value.type)
  emitUpdate()
}

// Watch local changes and emit immediately for all field types
watch(
  localRule,
  () => {
    emitUpdate()
  },
  { deep: true },
)

function toggle() {
  expanded.value = !expanded.value
}

function typeLabel(t: string) {
  const map: Record<string, string> = {
    text: '文本',
    semantic: '语义',
    image: '图片',
    api: 'API',
    external_data: '外部数据',
    multimodal_check: '多模态',
    image_consistency: '配图一致性',
    signature_compare: '签名对比',
  }
  return map[t] ?? t
}

function defaultConfig(type: string): RuleConfig {
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

</script>

<style scoped>
.rule-row {
  border: 1px solid #e8ecf0;
  border-radius: 8px;
  overflow: hidden;
}

.rule-row.expanded { border-color: #4f6ef7; }

.error-banner {
  background: #fff5f5;
  border-bottom: 1px solid #fed7d7;
  padding: 8px 16px;
}

.error-banner p {
  color: #c53030;
  font-size: 12px;
  margin: 0;
}

.rule-row-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  background: #fafbfc;
  transition: background 0.15s;
}

.rule-row-header:hover { background: #f0f3ff; }
.rule-row.expanded .rule-row-header { background: #f0f3ff; }

.rule-row-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.rule-index { font-size: 12px; color: #999; min-width: 24px; }
.rule-name-text { font-weight: 500; font-size: 14px; color: #333; }

.type-badge {
  font-size: 11px;
  background: #eef2ff;
  color: #4f6ef7;
  padding: 2px 6px;
  border-radius: 4px;
}

.disabled-badge {
  font-size: 11px;
  background: #f0f0f0;
  color: #999;
  padding: 2px 6px;
  border-radius: 4px;
}

.rule-row-actions { display: flex; align-items: center; gap: 6px; }

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

.expand-icon { font-size: 11px; color: #999; margin-left: 4px; }

.rule-form {
  padding: 20px;
  border-top: 1px solid #e8ecf0;
  background: #fff;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label { font-size: 13px; color: #555; font-weight: 500; }

.form-input {
  border: 1px solid #e0e6ed;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
  background: #fff;
  width: 100%;
}

.form-input:focus { border-color: #4f6ef7; }

.textarea-sm { height: 80px; resize: vertical; font-family: inherit; line-height: 1.5; }

.config-section { margin-top: 16px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.config-title { font-size: 13px; font-weight: 600; color: #666; margin-bottom: 12px; }

.form-row-inline { display: flex; gap: 16px; }
.form-row-inline .form-field { flex: 1; }

.toggle {
  display: flex;
  align-items: center;
  cursor: pointer;
  width: fit-content;
}

.toggle input { display: none; }

.toggle-slider {
  width: 36px;
  height: 20px;
  background: #e0e6ed;
  border-radius: 10px;
  position: relative;
  transition: background 0.2s;
}

.toggle-slider::after {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}

.toggle input:checked + .toggle-slider { background: #4f6ef7; }
.toggle input:checked + .toggle-slider::after { transform: translateX(16px); }
</style>
