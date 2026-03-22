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
          accept=".xlsx,.xls"
          style="display:none"
          @change="onFileChange"
        />
        <div v-if="!selectedFile" class="upload-placeholder">
          <div class="upload-icon">📄</div>
          <p>点击或拖拽上传 Excel 文件</p>
          <p class="upload-hint">支持 .xlsx / .xls，最大 20MB</p>
        </div>
        <div v-else class="upload-selected">
          <span class="file-icon">📊</span>
          <span class="file-name">{{ selectedFile.name }}</span>
          <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
          <button class="remove-btn" @click.stop="selectedFile = null">✕</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-header">
        <h2 class="section-title">检查规则 DSL</h2>
        <button class="btn-secondary" @click="loadExample">加载示例</button>
      </div>
      <textarea
        v-model="rulesText"
        class="rules-editor"
        placeholder='{"rules": [{"id": "r1", "name": "检查交付内容", "type": "text", "config": {"keywords": ["交付内容"]}}]}'
        spellcheck="false"
      />
      <div v-if="validateErrors.length" class="error-list">
        <p v-for="e in validateErrors" :key="e" class="error-item">⚠ {{ e }}</p>
      </div>
      <div v-if="rulesValid === true" class="success-msg">✓ 规则格式正确</div>
    </div>

    <div class="card">
      <h2 class="section-title">可选参数</h2>
      <div class="form-row">
        <label>报告类型</label>
        <input v-model="reportType" type="text" placeholder="如：交付报告、验收报告" class="form-input" />
      </div>
    </div>

    <div class="actions">
      <button class="btn-secondary" @click="validateOnly" :disabled="submitting">验证规则</button>
      <button class="btn-primary" @click="submit" :disabled="submitting || !selectedFile || !rulesText.trim()">
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

const router = useRouter()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const rulesText = ref('')
const reportType = ref('')
const isDragging = ref(false)
const submitting = ref(false)
const submitError = ref('')
const validateErrors = ref<string[]>([])
const rulesValid = ref<boolean | null>(null)

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) selectedFile.value = input.files[0]
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    selectedFile.value = file
  }
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
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
}

async function validateOnly() {
  validateErrors.value = []
  rulesValid.value = null
  let parsed: object
  try {
    parsed = JSON.parse(rulesText.value)
  } catch {
    validateErrors.value = ['JSON 格式错误']
    return
  }
  try {
    const res = await validateRules(parsed)
    validateErrors.value = res.errors
    rulesValid.value = res.valid
  } catch (e: unknown) {
    validateErrors.value = [(e as Error).message]
  }
}

async function submit() {
  submitError.value = ''
  if (!selectedFile.value) return
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
      reportType.value || undefined,
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
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-secondary:hover:not(:disabled) { background: #f0f3ff; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.error-banner {
  background: #fff5f5;
  border: 1px solid #fed7d7;
  color: #c53030;
  border-radius: 6px;
  padding: 12px 16px;
  font-size: 14px;
}
</style>
