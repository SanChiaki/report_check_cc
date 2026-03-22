<template>
  <div class="rule-config">
    <h1 class="page-title">规则配置</h1>

    <div class="card">
      <div class="section-header">
        <h2 class="section-title">规则列表</h2>
        <button class="btn-primary" @click="addRule">+ 新增规则</button>
      </div>

      <div v-if="rules.length === 0" class="empty-state">
        <p>暂无规则，点击「新增规则」开始配置</p>
      </div>

      <div v-else class="rule-list">
        <div
          v-for="(rule, idx) in rules"
          :key="rule.id"
          class="rule-row"
          :class="{ expanded: expandedIdx === idx }"
        >
          <div class="rule-row-header" @click="toggleExpand(idx)">
            <div class="rule-row-left">
              <span class="rule-index">#{{ idx + 1 }}</span>
              <span class="rule-name-text">{{ rule.name || '(未命名)' }}</span>
              <span class="type-badge">{{ typeLabel(rule.type) }}</span>
              <span v-if="rule.disabled" class="disabled-badge">已禁用</span>
            </div>
            <div class="rule-row-actions">
              <button class="icon-btn" @click.stop="moveUp(idx)" :disabled="idx === 0" title="上移">↑</button>
              <button class="icon-btn" @click.stop="moveDown(idx)" :disabled="idx === rules.length - 1" title="下移">↓</button>
              <button class="icon-btn danger" @click.stop="removeRule(idx)" title="删除">✕</button>
              <span class="expand-icon">{{ expandedIdx === idx ? '▲' : '▼' }}</span>
            </div>
          </div>

          <div v-if="expandedIdx === idx" class="rule-form">
            <div class="form-grid">
              <div class="form-field">
                <label>规则 ID</label>
                <input v-model="rule.id" type="text" class="form-input" placeholder="唯一标识，如 r1" />
              </div>
              <div class="form-field">
                <label>规则名称</label>
                <input v-model="rule.name" type="text" class="form-input" placeholder="如：检查交付内容" />
              </div>
              <div class="form-field">
                <label>规则类型</label>
                <select v-model="rule.type" class="form-input" @change="onTypeChange(rule)">
                  <option value="text">文本检查</option>
                  <option value="semantic">语义检查</option>
                  <option value="image">图片检查</option>
                  <option value="api">API 检查</option>
                  <option value="external_data">外部数据检查</option>
                </select>
              </div>
              <div class="form-field">
                <label>禁用</label>
                <label class="toggle">
                  <input type="checkbox" v-model="rule.disabled" />
                  <span class="toggle-slider" />
                </label>
              </div>
            </div>

            <!-- Text config -->
            <template v-if="rule.type === 'text'">
              <div class="config-section">
                <h3 class="config-title">文本检查配置</h3>
                <div class="form-field">
                  <label>关键词（每行一个）</label>
                  <textarea
                    :value="(rule.config.keywords || []).join('\n')"
                    @input="rule.config.keywords = ($event.target as HTMLTextAreaElement).value.split('\n').filter(Boolean)"
                    class="form-input textarea-sm"
                    placeholder="交付内容&#10;验收报告"
                  />
                </div>
                <div class="form-row-inline">
                  <div class="form-field">
                    <label>匹配模式</label>
                    <select v-model="rule.config.match_mode" class="form-input">
                      <option value="any">任意匹配 (any)</option>
                      <option value="all">全部匹配 (all)</option>
                      <option value="exact">精确匹配 (exact)</option>
                    </select>
                  </div>
                  <div class="form-field">
                    <label>区分大小写</label>
                    <label class="toggle">
                      <input type="checkbox" v-model="rule.config.case_sensitive" />
                      <span class="toggle-slider" />
                    </label>
                  </div>
                </div>
              </div>
            </template>

            <!-- Semantic config -->
            <template v-else-if="rule.type === 'semantic'">
              <div class="config-section">
                <h3 class="config-title">语义检查配置</h3>
                <div class="form-field">
                  <label>检查要求描述</label>
                  <textarea
                    v-model="rule.config.requirement"
                    class="form-input textarea-sm"
                    placeholder="移交记录中要包含移交人、移交时间、移交命令"
                  />
                </div>
              </div>
            </template>

            <!-- Image config -->
            <template v-else-if="rule.type === 'image'">
              <div class="config-section">
                <h3 class="config-title">图片检查配置</h3>
                <div class="form-field">
                  <label>图片内容要求</label>
                  <textarea
                    v-model="rule.config.requirement"
                    class="form-input textarea-sm"
                    placeholder="清理机房，图片应显示干净整洁的机房环境"
                  />
                </div>
                <div class="form-field">
                  <label>关键词过滤（附近文字，每行一个）</label>
                  <textarea
                    :value="(rule.config.nearby_keywords || []).join('\n')"
                    @input="rule.config.nearby_keywords = ($event.target as HTMLTextAreaElement).value.split('\n').filter(Boolean)"
                    class="form-input textarea-sm"
                    placeholder="机房&#10;清理"
                  />
                </div>
              </div>
            </template>

            <!-- API config -->
            <template v-else-if="rule.type === 'api'">
              <div class="config-section">
                <h3 class="config-title">API 检查配置</h3>
                <div class="form-field">
                  <label>提取内容描述</label>
                  <input v-model="rule.config.extract_description" type="text" class="form-input" placeholder="报告中的客户邮箱地址" />
                </div>
                <div class="form-field">
                  <label>API URL</label>
                  <input v-model="rule.config.api_url" type="text" class="form-input" placeholder="https://api.example.com/validate" />
                </div>
                <div class="form-field">
                  <label>请求方法</label>
                  <select v-model="rule.config.method" class="form-input">
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                  </select>
                </div>
              </div>
            </template>

            <!-- External data config -->
            <template v-else-if="rule.type === 'external_data'">
              <div class="config-section">
                <h3 class="config-title">外部数据检查配置</h3>
                <div class="form-field">
                  <label>提取内容描述</label>
                  <input v-model="rule.config.extract_description" type="text" class="form-input" placeholder="报告中的设备列表" />
                </div>
                <div class="form-field">
                  <label>外部数据 API URL</label>
                  <input v-model="rule.config.data_url" type="text" class="form-input" placeholder="https://api.example.com/devices" />
                </div>
                <div class="form-field">
                  <label>分析要求</label>
                  <textarea
                    v-model="rule.config.analysis_requirement"
                    class="form-input textarea-sm"
                    placeholder="报告中的设备是否全部包含在设备清单中"
                  />
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- DSL Preview -->
    <div class="card">
      <div class="section-header">
        <h2 class="section-title">DSL 预览</h2>
        <div class="preview-actions">
          <button class="btn-secondary" @click="copyDsl">{{ copied ? '已复制 ✓' : '复制' }}</button>
          <button class="btn-secondary" @click="validateDsl">验证</button>
        </div>
      </div>
      <pre class="dsl-preview">{{ dslJson }}</pre>
      <div v-if="validateErrors.length" class="error-list">
        <p v-for="e in validateErrors" :key="e" class="error-item">⚠ {{ e }}</p>
      </div>
      <div v-if="dslValid === true" class="success-msg">✓ 规则格式正确</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { validateRules } from '../api'

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
  [key: string]: unknown
}

interface Rule {
  id: string
  name: string
  type: string
  disabled: boolean
  config: RuleConfig
}

const rules = ref<Rule[]>([])
const expandedIdx = ref<number | null>(null)
const copied = ref(false)
const validateErrors = ref<string[]>([])
const dslValid = ref<boolean | null>(null)

function typeLabel(t: string) {
  const map: Record<string, string> = {
    text: '文本',
    semantic: '语义',
    image: '图片',
    api: 'API',
    external_data: '外部数据',
  }
  return map[t] ?? t
}

function defaultConfig(type: string): RuleConfig {
  if (type === 'text') return { keywords: [], match_mode: 'any', case_sensitive: false }
  if (type === 'semantic') return { requirement: '' }
  if (type === 'image') return { requirement: '', nearby_keywords: [] }
  if (type === 'api') return { extract_description: '', api_url: '', method: 'POST' }
  if (type === 'external_data') return { extract_description: '', data_url: '', analysis_requirement: '' }
  return {}
}

function addRule() {
  const idx = rules.value.length + 1
  rules.value.push({
    id: `r${idx}`,
    name: '',
    type: 'text',
    disabled: false,
    config: defaultConfig('text'),
  })
  expandedIdx.value = rules.value.length - 1
}

function removeRule(idx: number) {
  rules.value.splice(idx, 1)
  if (expandedIdx.value === idx) expandedIdx.value = null
}

function toggleExpand(idx: number) {
  expandedIdx.value = expandedIdx.value === idx ? null : idx
}

function moveUp(idx: number) {
  if (idx === 0) return
  const arr = rules.value
  ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
}

function moveDown(idx: number) {
  if (idx === rules.value.length - 1) return
  const arr = rules.value
  ;[arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]
}

function onTypeChange(rule: Rule) {
  rule.config = defaultConfig(rule.type)
}

const dslJson = computed(() => {
  const payload = {
    rules: rules.value.map((r) => {
      const obj: Record<string, unknown> = {
        id: r.id,
        name: r.name,
        type: r.type,
        config: r.config,
      }
      if (r.disabled) obj.disabled = true
      return obj
    }),
  }
  return JSON.stringify(payload, null, 2)
})

async function copyDsl() {
  await navigator.clipboard.writeText(dslJson.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

async function validateDsl() {
  validateErrors.value = []
  dslValid.value = null
  try {
    const parsed = JSON.parse(dslJson.value)
    const res = await validateRules(parsed)
    validateErrors.value = res.errors
    dslValid.value = res.valid
  } catch (e: unknown) {
    validateErrors.value = [(e as Error).message]
  }
}
</script>

<style scoped>
.rule-config { display: flex; flex-direction: column; gap: 20px; }

.page-title { font-size: 24px; font-weight: 600; color: #1a1a2e; }

.card {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}

.section-title { font-size: 15px; font-weight: 600; color: #333; }

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 14px;
}

.rule-list { display: flex; flex-direction: column; gap: 8px; }

.rule-row {
  border: 1px solid #e8ecf0;
  border-radius: 8px;
  overflow: hidden;
}

.rule-row.expanded { border-color: #4f6ef7; }

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

/* DSL Preview */
.preview-actions { display: flex; gap: 8px; }

.dsl-preview {
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 8px;
  padding: 16px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}

.error-list { margin-top: 10px; }
.error-item { color: #e53e3e; font-size: 13px; margin-bottom: 4px; }
.success-msg { color: #38a169; font-size: 13px; margin-top: 10px; }

.btn-primary {
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-primary:hover { background: #3a5ae8; }

.btn-secondary {
  background: #fff;
  color: #4f6ef7;
  border: 1px solid #4f6ef7;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-secondary:hover { background: #f0f3ff; }
</style>
