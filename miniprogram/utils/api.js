var SETTINGS_DEFAULTS = {
  api_base: 'http://127.0.0.1:8000',
  hints_on: false,
  llm_base_url: '',
  llm_api_key: '',
  llm_model: ''
}

function getSettings() {
  var s = {}
  try {
    s = wx.getStorageSync('settings') || {}
  } catch (e) {
    s = {}
  }
  var merged = {}
  var k
  for (k in SETTINGS_DEFAULTS) {
    merged[k] = SETTINGS_DEFAULTS[k]
  }
  for (k in s) {
    merged[k] = s[k]
  }
  return merged
}

function apiBase() {
  var base = getSettings().api_base || SETTINGS_DEFAULTS.api_base
  return String(base).replace(/\/+$/, '')
}

function buildLlm(settings) {
  var s = settings || getSettings()
  var obj = {}
  if (s.llm_base_url) obj.base_url = s.llm_base_url
  if (s.llm_api_key) obj.api_key = s.llm_api_key
  if (s.llm_model) obj.model = s.llm_model
  return Object.keys(obj).length ? obj : null
}

function toast(title) {
  if (!title) return
  var msg = String(title)
  if (msg.length > 20) msg = msg.slice(0, 20)
  wx.showToast({ title: msg, icon: 'none' })
}

function request(path, method, data) {
  return new Promise(function (resolve, reject) {
    wx.request({
      url: apiBase() + path,
      method: method || 'GET',
      data: data || {},
      header: { 'Content-Type': 'application/json' },
      success: function (res) {
        var status = res.statusCode
        var body = res.data
        if (status >= 200 && status < 300) {
          resolve(body)
          return
        }
        var detail = body && (body.detail || body.message)
        var msg = detail || ('HTTP ' + status)
        toast(msg)
        reject(new Error(detail || ('HTTP ' + status)))
      },
      fail: function (err) {
        var msg = '网络请求失败，请检查 API 地址与「不校验合法域名」设置'
        toast(msg)
        reject(new Error(msg + (err && err.errMsg ? '：' + err.errMsg : '')))
      }
    })
  })
}

function cleanSeed(seed) {
  if (seed === undefined || seed === null || seed === '') return undefined
  return seed
}

function createSession(opts) {
  opts = opts || {}
  return request('/api/phase5/session', 'POST', {
    seed: cleanSeed(opts.seed),
    ai_strengths: opts.aiStrengths || ['mid', 'mid', 'mid'],
    hints_on: !!opts.hintsOn,
    llm: opts.llm === undefined ? buildLlm() : opts.llm
  })
}

function getSession(sid) {
  return request('/api/phase5/session/' + encodeURIComponent(sid), 'GET')
}

function act(sid, action) {
  return request('/api/phase5/session/' + encodeURIComponent(sid) + '/act', 'POST', { action: action })
}

function advise(sid) {
  return request('/api/phase5/session/' + encodeURIComponent(sid) + '/advise', 'POST', {})
}

function deleteSession(sid) {
  return request('/api/phase5/session/' + encodeURIComponent(sid), 'DELETE')
}

function review(opts) {
  opts = opts || {}
  return request('/api/phase6/review', 'POST', {
    record: opts.record,
    seed: cleanSeed(opts.seed),
    hints_on: !!opts.hintsOn,
    llm: opts.llm === undefined ? buildLlm() : opts.llm,
    seat_focus: opts.seatFocus
  })
}

function score(opts) {
  opts = opts || {}
  return request('/api/phase7/score', 'POST', {
    record: opts.record,
    seed: cleanSeed(opts.seed),
    rules: opts.rules,
    base: opts.base
  })
}

module.exports = {
  getSettings: getSettings,
  apiBase: apiBase,
  buildLlm: buildLlm,
  toast: toast,
  request: request,
  createSession: createSession,
  getSession: getSession,
  act: act,
  advise: advise,
  deleteSession: deleteSession,
  review: review,
  score: score
}
