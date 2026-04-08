<template>
  <div class="rule-config">
    <h1 class="page-title">规则配置</h1>

    <div class="card">
      <div class="section-header">
        <h2 class="section-title">规则列表</h2>
        <button class="btn-primary" @click="ruleListRef?.addRule()">+ 新增规则</button>
      </div>

      <RuleList
        ref="ruleListRef"
        :rules="rules"
        :errors="validateErrors"
        @update:rules="onRulesUpdate"
      />
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
        <p v-for="(e, i) in validateErrors" :key="i" class="error-item">⚠ [{{ e.rule_id }}] {{ e.message }}</p>
      </div>
      <div v-if="dslValid === true" class="success-msg">✓ 规则格式正确</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { validateRules } from '../api'
import RuleList from '../components/RuleList.vue'

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

const rules = ref<Rule[]>([])
const ruleListRef = ref<InstanceType<typeof RuleList> | null>(null)
const copied = ref(false)
const validateErrors = ref<Array<{ rule_id: string; field: string; message: string }>>([])
const dslValid = ref<boolean | null>(null)

function onRulesUpdate(updatedRules: Rule[]) {
  rules.value = updatedRules
  // Clear validation errors when rules change
  validateErrors.value = []
  dslValid.value = null
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
    validateErrors.value = res.errors as typeof validateErrors.value
    dslValid.value = res.valid
  } catch (e: unknown) {
    validateErrors.value = [{ rule_id: '', field: '', message: (e as Error).message }]
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
