<template>
  <div class="check-page">
    <h1 class="page-title">提交报告检查</h1>

    <div class="card">
      <h2 class="section-title">上传报告</h2>
      <div
        class="upload-zone"
        :class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="onDrop"
        @click="fileInput?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.xls,.pdf,.msg"
          style="display:none"
          @change="onFileChange"
        />
        <div v-if="!selectedFile" class="upload-placeholder">
          <div class="upload-icon">📄</div>
          <p>点击或拖拽上传报告文件</p>
          <p class="upload-hint">支持 Excel (.xlsx / .xls)、PDF (.pdf) 和邮件 (.msg)，最大 20MB</p>
        </div>
        <div v-else class="upload-selected">
          <span class="file-icon">{{ getFileIcon(selectedFile.name) }}</span>
          <span class="file-name">{{ selectedFile.name }}</span>
          <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
          <button class="remove-btn" @click.stop="selectedFile = null">✕</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-header">
        <h2 class="section-title">检查规则</h2>
        <button class="btn-secondary" @click="loadExample">加载示例</button>
      </div>

      <!-- Raw DSL editor -->
      <textarea
        v-model="rulesText"
        class="rules-editor"
        placeholder='{"rules": [{"id": "r1", "name": "检查交付内容", "type": "text", "config": {"keywords": ["交付内容"]}}]}'
        spellcheck="false"
        @input="onTextareaInput"
      />
      <div v-if="jsonParseError" class="error-banner">{{ jsonParseError }}</div>
      <div v-else-if="validateErrors.length" class="error-list">
        <p v-for="(e, i) in validateErrors" :key="i" class="error-item">⚠ [{{ e.rule_id }}] {{ e.message }}</p>
      </div>
      <div v-else-if="rulesValid === true" class="success-msg">✓ 规则格式正确</div>

      <!-- Visual rule editor -->
      <div v-if="!jsonParseError && rules.length > 0" class="rule-list-wrapper">
        <div class="section-header" style="margin-top: 20px;">
          <span class="section-title">可视化编辑</span>
          <button class="btn-secondary" @click="ruleListRef?.addRule()">+ 新增规则</button>
        </div>
        <RuleList
          ref="ruleListRef"
          :rules="rules"
          :errors="validateErrors"
          @update:rules="onRulesUpdate"
        />
      </div>
    </div>

    <div class="actions">
      <button class="btn-primary" @click="submit" :disabled="submitting || !selectedFile || !!jsonParseError || rules.length === 0">
        {{ submitting ? '提交中...' : '提交检查' }}
      </button>
    </div>

    <div v-if="submitError" class="error-banner">{{ submitError }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { submitCheck, validateRules } from '../api'
import RuleList from '../components/RuleList.vue'
import { useDebounceFn } from '../utils/useDebounce'

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

const router = useRouter()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const rulesText = ref('')
const rules = ref<Rule[]>([])
const isDragging = ref(false)
const submitting = ref(false)
const submitError = ref('')
const jsonParseError = ref('')
const validateErrors = ref<Array<{ rule_id: string; field: string; message: string }>>([])
const rulesValid = ref<boolean | null>(null)
const ruleListRef = ref<InstanceType<typeof RuleList> | null>(null)

// Sync textarea → rules[] (debounced 300ms)
const debouncedParse = useDebounceFn((text: string) => {
  try {
    const parsed = JSON.parse(text)
    if (Array.isArray(parsed)) {
      // Plain array — wrap in {rules: []}
      rules.value = parsed as Rule[]
    } else if (parsed.rules && Array.isArray(parsed.rules)) {
      rules.value = parsed.rules as Rule[]
    } else {
      rules.value = []
    }
    jsonParseError.value = ''
  } catch {
    jsonParseError.value = 'JSON 格式错误'
  }
}, 300)

// Auto-validate (debounced 500ms)
const debouncedValidate = useDebounceFn(async (text: string) => {
  if (!text.trim()) {
    validateErrors.value = []
    rulesValid.value = null
    return
  }
  try {
    const parsed = JSON.parse(text)
    const res = await validateRules(parsed)
    validateErrors.value = res.errors as typeof validateErrors.value
    rulesValid.value = res.valid
  } catch {
    // JSON parse errors handled separately
  }
}, 500)

function onTextareaInput() {
  jsonParseError.value = ''
  debouncedParse(rulesText.value)
  debouncedValidate(rulesText.value)
}

// Sync rules[] → textarea (immediate, no debounce)
function onRulesUpdate(updatedRules: Rule[]) {
  rules.value = updatedRules
  const payload = {
    rules: updatedRules.map((r) => {
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
  rulesText.value = JSON.stringify(payload, null, 2)
  rulesValid.value = null
  validateErrors.value = []
  debouncedValidate.cancel()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) selectedFile.value = input.files[0]
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls') || file.name.endsWith('.pdf') || file.name.endsWith('.msg'))) {
    selectedFile.value = file
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function getFileIcon(fileName: string) {
  if (fileName.endsWith('.pdf')) return '📕'
  if (fileName.endsWith('.msg')) return '✉️'
  if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) return '📊'
  return '📄'
}

function loadExample() {
  rulesText.value = JSON.stringify({
    rules: [
      {
        id: 'r1',
        name: '检查交付内容章节',
        type: 'text',
        config: { keywords: ['交付内容'], match_mode: 'any' },
      },
      {
        id: 'r2',
        name: '移交记录完整性',
        type: 'semantic',
        config: { requirement: '移交记录中要包含移交人、移交时间、移交命令' },
      },
      {
        id: 'r3',
        name: '机房清理图片',
        type: 'image',
        config: { requirement: '清理机房，图片应显示干净整洁的机房环境' },
      },
    ],
  }, null, 2)
  rulesValid.value = null
  validateErrors.value = []
  debouncedParse(rulesText.value)
  debouncedValidate(rulesText.value)
}

async function submit() {
  submitError.value = ''
  if (!selectedFile.value) return
  if (rules.value.length === 0) return
  let parsed: object
  try {
    parsed = JSON.parse(rulesText.value)
  } catch {
    submitError.value = 'JSON 格式错误，请检查规则 DSL'
    return
  }
  submitting.value = true
  try {
    const res = await submitCheck(
      selectedFile.value,
      parsed,
    )
    router.push(`/result/${res.task_id}`)
  } catch (e: unknown) {
    submitError.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.check-page { display: flex; flex-direction: column; gap: 20px; }

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a2e;
}

.card {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header .section-title { margin-bottom: 0; }

.rule-list-wrapper {
  border-top: 1px solid #f0f0f0;
  padding-top: 16px;
}

.upload-zone {
  border: 2px dashed #d0d7e3;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.upload-zone:hover, .upload-zone.drag-over {
  border-color: #4f6ef7;
  background: #f0f3ff;
}

.upload-zone.has-file {
  border-style: solid;
  border-color: #4f6ef7;
  background: #f8f9ff;
}

.upload-icon { font-size: 40px; margin-bottom: 12px; }
.upload-placeholder p { color: #666; font-size: 14px; }
.upload-hint { font-size: 12px; color: #999; margin-top: 4px; }

.upload-selected {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.file-icon { font-size: 24px; }
.file-name { font-weight: 500; color: #333; }
.file-size { color: #999; font-size: 13px; }

.remove-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 16px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.2s, background 0.2s;
}

.remove-btn:hover { color: #e53e3e; background: #fff0f0; }

.rules-editor {
  width: 100%;
  height: 200px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  border: 1px solid #e0e6ed;
  border-radius: 6px;
  padding: 12px;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
  line-height: 1.6;
}

.rules-editor:focus { border-color: #4f6ef7; }

.error-list { margin-top: 10px; }
.error-item { color: #e53e3e; font-size: 13px; margin-bottom: 4px; }
.success-msg { color: #38a169; font-size: 13px; margin-top: 10px; }

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-row label { font-size: 14px; color: #555; min-width: 80px; }

.form-input {
  flex: 1;
  border: 1px solid #e0e6ed;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus { border-color: #4f6ef7; }

.actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn-primary {
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 10px 24px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s, opacity 0.2s;
}

.btn-primary:hover:not(:disabled) { background: #3a5ae8; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

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

.error-banner {
  background: #fff5f5;
  border: 1px solid #fed7d7;
  color: #c53030;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  margin-top: 8px;
}
</style>
