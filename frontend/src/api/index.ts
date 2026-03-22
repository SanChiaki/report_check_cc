const BASE = '/api/v1'

export interface SubmitResponse {
  task_id: string
  status: string
  message: string
}

export interface LocationInfo {
  type: string
  value: string
  context: string
}

export interface CheckResultItem {
  rule_id: string
  rule_name: string
  rule_type: string
  status: 'passed' | 'failed' | 'error'
  location: LocationInfo
  message: string
  suggestion: string
  example: string
  confidence: number
}

export interface CheckSummary {
  total: number
  passed: number
  failed: number
  error: number
}

export interface CheckResultData {
  report_info: { file_name: string; report_type: string | null }
  results: CheckResultItem[]
  summary: CheckSummary
}

export interface CheckResultResponse {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  result?: CheckResultData
  error?: string
}

export interface ValidateResponse {
  valid: boolean
  errors: string[]
}

export interface Template {
  id: number
  name: string
  report_type: string
  rules: object
}

export async function submitCheck(
  file: File,
  rules: object,
  reportType?: string,
  contextVars?: object,
): Promise<SubmitResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('rules', JSON.stringify(rules))
  if (reportType) form.append('report_type', reportType)
  if (contextVars) form.append('context_vars', JSON.stringify(contextVars))

  const res = await fetch(`${BASE}/check/submit`, { method: 'POST', body: form })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '提交失败')
  }
  return res.json()
}

export async function getResult(taskId: string): Promise<CheckResultResponse> {
  const res = await fetch(`${BASE}/check/result/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '获取结果失败')
  }
  return res.json()
}

export async function validateRules(rules: object): Promise<ValidateResponse> {
  const res = await fetch(`${BASE}/rules/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rules),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '验证失败')
  }
  return res.json()
}

export async function listTemplates(reportType?: string): Promise<Template[]> {
  const url = reportType
    ? `${BASE}/templates?report_type=${encodeURIComponent(reportType)}`
    : `${BASE}/templates`
  const res = await fetch(url)
  if (!res.ok) throw new Error('获取模板失败')
  const data = await res.json()
  return data.templates
}
