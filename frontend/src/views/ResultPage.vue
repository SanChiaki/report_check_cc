<template>
  <div class="result-page">
    <div class="page-header">
      <router-link to="/" class="back-link">← 返回</router-link>
      <h1 class="page-title">检查结果</h1>
    </div>

    <!-- Loading / polling -->
    <div v-if="status === 'pending' || status === 'processing'" class="card status-card">
      <div class="spinner" />
      <div class="status-info">
        <p class="status-label">{{ status === 'pending' ? '排队中...' : '检查中...' }}</p>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progress + '%' }" />
        </div>
        <p class="progress-text">{{ progress }}%</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="status === 'failed'" class="card error-card">
      <p class="error-title">检查失败</p>
      <p class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- Results -->
    <template v-else-if="status === 'completed' && result">
      <!-- Summary -->
      <div class="card summary-card">
        <div class="summary-info">
          <span class="file-name">{{ result.report_info.file_name }}</span>
          <span v-if="result.report_info.report_type" class="report-type">{{ result.report_info.report_type }}</span>
        </div>
        <div class="summary-stats">
          <div class="stat total">
            <span class="stat-num">{{ result.summary.total }}</span>
            <span class="stat-label">总计</span>
          </div>
          <div class="stat passed">
            <span class="stat-num">{{ result.summary.passed }}</span>
            <span class="stat-label">通过</span>
          </div>
          <div class="stat failed">
            <span class="stat-num">{{ result.summary.failed }}</span>
            <span class="stat-label">未通过</span>
          </div>
          <div class="stat error">
            <span class="stat-num">{{ result.summary.error }}</span>
            <span class="stat-label">错误</span>
          </div>
        </div>
        <div class="pass-rate">
          <div class="pass-bar">
            <div
              class="pass-fill"
              :style="{ width: passRate + '%' }"
              :class="passRate === 100 ? 'all-pass' : passRate >= 60 ? 'partial' : 'low'"
            />
          </div>
          <span class="pass-pct">通过率 {{ passRate }}%</span>
        </div>
      </div>

      <!-- Result items -->
      <div class="results-list">
        <div
          v-for="item in result.results"
          :key="item.rule_id"
          class="result-item card"
          :class="item.status"
        >
          <div class="item-header">
            <div class="item-left">
              <span class="status-badge" :class="item.status">
                {{ statusLabel(item.status) }}
              </span>
              <span class="rule-name">{{ item.rule_name }}</span>
              <span class="rule-type-badge">{{ typeLabel(item.rule_type) }}</span>
            </div>
            <span class="confidence" v-if="item.status !== 'error'">
              置信度 {{ Math.round(item.confidence * 100) }}%
            </span>
          </div>

          <p v-if="item.message" class="item-message">{{ item.message }}</p>

          <div v-if="item.location?.value" class="location-info">
            <span class="location-label">位置：</span>
            <span class="location-value">{{ item.location.value }}</span>
            <span v-if="item.location.context" class="location-context">— {{ item.location.context }}</span>
          </div>

          <div v-if="item.suggestion" class="suggestion">
            <span class="suggestion-label">建议：</span>{{ item.suggestion }}
          </div>

          <div v-if="item.example" class="example">
            <span class="example-label">示例：</span>{{ item.example }}
          </div>
        </div>
      </div>
    </template>

    <div v-if="fetchError" class="error-banner">{{ fetchError }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getResult, type CheckResultData } from '../api'

const route = useRoute()
const taskId = route.params.taskId as string

const status = ref<string>('pending')
const progress = ref(0)
const result = ref<CheckResultData | null>(null)
const errorMsg = ref('')
const fetchError = ref('')
let pollTimer: ReturnType<typeof setTimeout> | null = null

const passRate = computed(() => {
  if (!result.value || result.value.summary.total === 0) return 0
  return Math.round((result.value.summary.passed / result.value.summary.total) * 100)
})

function statusLabel(s: string) {
  return s === 'passed' ? '✓ 通过' : s === 'failed' ? '✗ 未通过' : '! 错误'
}

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

async function poll() {
  try {
    const res = await getResult(taskId)
    status.value = res.status
    progress.value = res.progress
    if (res.result) result.value = res.result
    if (res.error) errorMsg.value = res.error

    if (res.status === 'pending' || res.status === 'processing') {
      pollTimer = setTimeout(poll, 2000)
    }
  } catch (e: unknown) {
    fetchError.value = (e as Error).message
  }
}

onMounted(poll)
onUnmounted(() => { if (pollTimer) clearTimeout(pollTimer) })
</script>

<style scoped>
.result-page { display: flex; flex-direction: column; gap: 20px; }

.page-header { display: flex; align-items: center; gap: 16px; }
.back-link { color: #666; font-size: 14px; }
.back-link:hover { color: #4f6ef7; }
.page-title { font-size: 24px; font-weight: 600; color: #1a1a2e; }

.card {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}

/* Status card */
.status-card {
  display: flex;
  align-items: center;
  gap: 20px;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e0e6ed;
  border-top-color: #4f6ef7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

.status-info { flex: 1; }
.status-label { font-size: 15px; color: #555; margin-bottom: 10px; }

.progress-bar {
  height: 6px;
  background: #e8ecf0;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 6px;
}

.progress-fill {
  height: 100%;
  background: #4f6ef7;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.progress-text { font-size: 13px; color: #999; }

/* Error card */
.error-card { border-left: 4px solid #e53e3e; }
.error-title { font-weight: 600; color: #c53030; margin-bottom: 8px; }
.error-msg { color: #666; font-size: 14px; }

/* Summary */
.summary-card { }
.summary-info { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.file-name { font-weight: 600; font-size: 15px; color: #333; }
.report-type {
  background: #eef2ff;
  color: #4f6ef7;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
}

.summary-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
}

.stat { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.stat-num { font-size: 28px; font-weight: 700; }
.stat-label { font-size: 12px; color: #999; }
.stat.total .stat-num { color: #333; }
.stat.passed .stat-num { color: #38a169; }
.stat.failed .stat-num { color: #e53e3e; }
.stat.error .stat-num { color: #dd6b20; }

.pass-rate { display: flex; align-items: center; gap: 12px; }
.pass-bar { flex: 1; height: 8px; background: #e8ecf0; border-radius: 4px; overflow: hidden; }
.pass-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
.pass-fill.all-pass { background: #38a169; }
.pass-fill.partial { background: #ecc94b; }
.pass-fill.low { background: #e53e3e; }
.pass-pct { font-size: 13px; color: #666; white-space: nowrap; }

/* Result items */
.results-list { display: flex; flex-direction: column; gap: 12px; }

.result-item { border-left: 4px solid #e8ecf0; }
.result-item.passed { border-left-color: #38a169; }
.result-item.failed { border-left-color: #e53e3e; }
.result-item.error { border-left-color: #dd6b20; }

.item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.item-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.status-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
}

.status-badge.passed { background: #f0fff4; color: #276749; }
.status-badge.failed { background: #fff5f5; color: #c53030; }
.status-badge.error { background: #fffaf0; color: #c05621; }

.rule-name { font-weight: 600; font-size: 14px; color: #333; }

.rule-type-badge {
  font-size: 11px;
  background: #f0f3ff;
  color: #4f6ef7;
  padding: 2px 6px;
  border-radius: 4px;
}

.confidence { font-size: 12px; color: #999; }

.item-message { font-size: 14px; color: #555; margin-bottom: 8px; }

.location-info {
  font-size: 13px;
  color: #666;
  background: #f8f9fa;
  border-radius: 4px;
  padding: 6px 10px;
  margin-bottom: 8px;
}

.location-label { font-weight: 500; color: #444; }
.location-value { color: #4f6ef7; font-family: monospace; }
.location-context { color: #999; }

.suggestion {
  font-size: 13px;
  color: #555;
  margin-bottom: 6px;
}

.suggestion-label { font-weight: 500; color: #dd6b20; }

.example {
  font-size: 13px;
  color: #555;
  background: #f8f9fa;
  border-radius: 4px;
  padding: 6px 10px;
  font-family: monospace;
}

.example-label { font-weight: 500; color: #666; font-family: sans-serif; }

.error-banner {
  background: #fff5f5;
  border: 1px solid #fed7d7;
  color: #c53030;
  border-radius: 6px;
  padding: 12px 16px;
  font-size: 14px;
}
</style>
