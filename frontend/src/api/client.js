// REST API 客户端（Cookie 会话 + 统一错误结构 {code,message,detail}）
const BASE = ''

async function request(method, path, body) {
  const opts = {
    method,
    credentials: 'include',
    headers: {}
  }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const resp = await fetch(BASE + path, opts)
  if (resp.status === 401) {
    // 登录态失效 → 跳登录页（由 authStore 处理）
    window.dispatchEvent(new CustomEvent('auth:expired'))
    throw new Error('登录态已过期')
  }
  const text = await resp.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!resp.ok) {
    const msg = (data && data.message) || `请求失败(${resp.status})`
    const err = new Error(msg)
    err.status = resp.status
    err.code = data && data.code
    err.detail = data && data.detail
    throw err
  }
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  put: (p, b) => request('PUT', p, b),
  del: (p) => request('DELETE', p),

  // 附件上传（multipart）
  upload(formData) {
    return fetch(BASE + '/api/attachments/upload', {
      method: 'POST',
      credentials: 'include',
      body: formData
    }).then(async (resp) => {
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.message || '上传失败')
      return data
    })
  },

  // 附件：列表 / 删除 / 下载
  attachmentsList: (conversationId) =>
    request('GET', `/api/attachments/list?conversation_id=${encodeURIComponent(conversationId)}`),
  attachmentDel: (attId) => request('DELETE', `/api/attachments/${attId}`),
  attachmentDownloadUrl: (attId) => BASE + `/api/attachments/${attId}/download`
}
