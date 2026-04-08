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
        <div class="example-selector">
          <select v-model="selectedTemplate" @change="onTemplateChange" class="template-select">
            <option value="">选择模板...</option>
            <option value="kickoff">开工报告</option>
            <option value="progress">进度报告（EISDP）</option>
            <option value="quality">质量报告</option>
            <option value="completion">完工报告</option>
          </select>
        </div>
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
const selectedTemplate = ref('')

const ruleTemplates: Record<string, { rules: Rule[] }> = {
  kickoff: {
    rules: [
      {
        id: 'r1',
        name: '交付内容语义识别',
        type: 'semantic',
        config: { requirement: '报告中是否存在"交付内容"相关的内容，需通过语义理解确认交付内容的具体描述' },
      },
      {
        id: 'r2',
        name: '主要产品设备信息',
        type: 'text',
        config: { keywords: ['设备', '产品', '型号', '规格'], match_mode: 'any' },
      },
      {
        id: 'r3',
        name: '交付计划时间逻辑校验',
        type: 'semantic',
        config: { requirement: '交付计划中包含时间描述，判断时间是否符合逻辑，例如开工报告发送日期不得早于开工日期' },
      },
    ],
  },
  progress: {
    rules: [
      {
        id: 'r1',
        name: '仪表盘信息完整性',
        type: 'semantic',
        config: { requirement: '项目仪表盘中的每一项都需要填写，不能有空的字段' },
      },
      {
        id: 'r2',
        name: '整体进展与进度一致性',
        type: 'semantic',
        config: { requirement: '整体进展模块需描述项目的整体进展和进度，且报告进度要与项目仪表盘中的进度信息一致' },
      },
      {
        id: 'r3',
        name: '风险及问题三要素检查',
        type: 'semantic',
        config: { requirement: '报告中必须有描述项目当前风险的模块，当内容不为空时，每一项都需要包含三要素：1）问题或风险描述；2）责任人；3）完成时间' },
      },
      {
        id: 'r4',
        name: '当前进展与周期匹配',
        type: 'semantic',
        config: { requirement: '进展内容需要和报告周期（日报、周报、双周报、月报，根据报告日期判断）相匹配' },
      },
      {
        id: 'r5',
        name: '下期计划时间校验',
        type: 'semantic',
        config: { requirement: '下期计划描述未来需要完成的事情，计划中的时间不得早于报告日期' },
      },
    ],
  },
  quality: {
    rules: [
      {
        id: 'r1',
        name: '质检总结完整性',
        type: 'semantic',
        config: { requirement: '说明质检的主要设备、质检的结论，如果质检不通过，必须包含问题描述' },
      },
      {
        id: 'r2',
        name: '质检明细配图一致性',
        type: 'image_consistency',
        config: { requirement: '检查质检明细中的每个检查项是否都有对应的现场照片证明，且图片内容符合检查项描述', strict_mode: false },
      },
    ],
  },
  completion: {
    rules: [
      {
        id: 'r1',
        name: '交付内容语义识别',
        type: 'semantic',
        config: { requirement: '报告中是否存在"交付内容"相关的内容，需通过语义理解确认交付内容的具体描述' },
      },
      {
        id: 'r2',
        name: '主要产品设备信息',
        type: 'text',
        config: { keywords: ['设备', '产品', '型号', '规格'], match_mode: 'any' },
      },
      {
        id: 'r3',
        name: '文档移交记录',
        type: 'semantic',
        config: { requirement: '报告中包含项目涉及的文档移交记录，需要有文档名、数量、接收人、移交时间' },
      },
      {
        id: 'r4',
        name: '账号密码移交记录',
        type: 'semantic',
        config: { requirement: '报告中包含账号密码移交内容，包含密码类型、数量、对应的设备、接收人、移交时间' },
      },
      {
        id: 'r5',
        name: '客户培训记录',
        type: 'semantic',
        config: { requirement: '报告中包含对客户的培训记录，包含培训主题、培训时间、参培人员名字' },
      },
    ],
  },
}

function onTemplateChange() {
  const template = ruleTemplates[selectedTemplate.value]
  if (!template) {
    rulesText.value = ''
    rules.value = []
    rulesValid.value = null
    validateErrors.value = []
    return
  }
  const payload = {
    rules: template.rules.map((r) => {
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
  debouncedParse(rulesText.value)
  debouncedValidate(rulesText.value)
}

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

.example-selector { display: flex; align-items: center; }

.template-select {
  border: 1px solid #4f6ef7;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #4f6ef7;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition: background 0.2s;
}

.template-select:hover { background: #f0f3ff; }

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
