var api = require('../../utils/api')
var viewmap = require('../../utils/viewmap')

var PHASE_TAGS = {
  turn_action: '摸打',
  claim: '申索',
  win: '胡牌',
  over: '流局'
}

var ACTION_LABELS = viewmap.ACTION_LABELS || {}

function seatText(seat) {
  if (seat === undefined || seat === null || seat < 0) return ''
  return seat === 0 ? '我（座0）' : '座' + seat
}

function phaseTag(phase) {
  return PHASE_TAGS[phase] || phase || ''
}

function actionText(action) {
  if (!action || !action.kind) return ''
  var label = ACTION_LABELS[action.kind] || action.kind
  var text = label
  if (action.tile) text += ' ' + action.tile
  if (action.from !== undefined && action.from !== null) text += '（来自座' + action.from + '）'
  return text
}

function byText(by) {
  if (by === 'tsumo') return '自摸'
  if (by === 'ron') return '点炮'
  return by || ''
}

Page({
  data: {
    loading: true,
    error: false,
    result: null,
    steps: [],
    idx: 0,
    total: 0,
    current: null,
    tally: [],
    winners: [],
    numEvents: 0,
    hasOver: false,
    summaryOpen: true
  },

  onLoad: function (query) {
    query = query || {}
    var record = null
    var seed = null
    if (query.from === 'practice') {
      var app = getApp()
      var payload = (app && app.globalData && app.globalData.reviewPayload) || null
      if (payload && payload.record) {
        record = payload.record
      } else if (payload && payload.seed !== undefined && payload.seed !== null && payload.seed !== '') {
        seed = payload.seed
      }
    }
    if (seed === null && query.seed !== undefined && query.seed !== '') {
      seed = query.seed
    }
    this.record = record
    this.seed = seed
    this.fetch()
  },

  fetch: function () {
    var that = this
    if (this.record === null && (this.seed === null || this.seed === '')) {
      this.setData({ loading: false, error: true })
      api.toast('缺少牌谱或种子号')
      return
    }
    var settings = api.getSettings()
    this.setData({ loading: true, error: false })
    api.review({
      record: this.record || undefined,
      seed: this.record ? undefined : this.seed,
      hintsOn: !!settings.hints_on,
      llm: api.buildLlm(settings)
    }).then(function (result) {
      var steps = (result && result.steps) || []
      that.setData({
        loading: false,
        error: false,
        result: result,
        steps: steps,
        total: steps.length,
        tally: that.buildTally(steps),
        winners: that.collectWinners(steps),
        numEvents: that.countEvents(result && result.summary),
        hasOver: steps.some(function (s) { return s && s.phase === 'over' })
      })
      that.setCurrent(0)
    }).catch(function () {
      that.setData({ loading: false, error: true })
    })
  },

  setCurrent: function (i) {
    var steps = this.data.steps
    var total = steps.length
    if (!total) {
      this.setData({ current: null, idx: 0 })
      return
    }
    if (i < 0) i = 0
    if (i > total - 1) i = total - 1
    var step = steps[i]
    var cur = this.decorate(step)
    this.setData({ idx: i, current: cur })
  },

  decorate: function (step) {
    if (!step) return null
    var cur = {}
    for (var k in step) {
      cur[k] = step[k]
    }
    cur.phaseTag = phaseTag(step.phase)
    cur.seatText = seatText(step.seat)
    cur.actionText = actionText(step.actual_action)
    cur.hasView = !!step.view
    if (step.fans) {
      cur.fansByText = byText(step.fans.by)
      cur.fanItems = step.fans.items || []
    }
    if (step.score) {
      cur.payerSeats = step.score.payer_seats || []
      cur.payerText = (cur.payerSeats.map(function (s) { return seatText(s) })).join('、')
    }
    if (step.advice) {
      var a = step.advice
      cur.hasLlm = !!a.advice
      cur.llm = a.advice || null
      cur.adviceError = a.error || ''
      var analysis = a.analysis || null
      var rec = analysis && analysis.recommend
      if (rec && rec.code) {
        cur.hard = {
          code: rec.code,
          ukeire_count: rec.ukeire_count,
          shanten_after: rec.shanten_after,
          hasUkeire: rec.ukeire_count !== undefined && rec.ukeire_count !== null,
          hasShanten: rec.shanten_after !== undefined && rec.shanten_after !== null
        }
      } else {
        cur.hard = null
      }
    }
    return cur
  },

  buildTally: function (steps) {
    var rows = []
    var s
    for (s = 0; s < 4; s++) {
      rows.push({ seat: s, seatText: seatText(s), decisions: 0, winBy: '', claims: 0 })
    }
    ;(steps || []).forEach(function (step) {
      if (!step) return
      var seat = step.seat
      if (seat < 0 || seat > 3) return
      if (step.phase === 'turn_action' || step.phase === 'claim') {
        rows[seat].decisions++
      }
      if (step.phase === 'win' && step.fans) {
        rows[seat].winBy = byText(step.fans.by)
      }
      if (step.phase === 'claim' && step.actual_action && step.actual_action.kind && step.actual_action.kind !== 'pass') {
        rows[seat].claims++
      }
    })
    return rows
  },

  collectWinners: function (steps) {
    var list = []
    ;(steps || []).forEach(function (step, i) {
      if (step && step.phase === 'win') {
        list.push({
          key: 'w' + i,
          seatText: seatText(step.seat),
          tile: step.tile || '',
          byText: step.fans ? byText(step.fans.by) : byText(step.actual_action && step.actual_action.kind)
        })
      }
    })
    return list
  },

  countEvents: function (summary) {
    var events = (summary && summary.events) || {}
    var n = 0
    var k
    for (k in events) {
      n += events[k] || 0
    }
    return n
  },

  onPrev: function () {
    if (this.data.idx > 0) this.setCurrent(this.data.idx - 1)
  },

  onNext: function () {
    if (this.data.idx < this.data.total - 1) this.setCurrent(this.data.idx + 1)
  },

  onRetry: function () {
    this.fetch()
  },

  onToggleSummary: function () {
    this.setData({ summaryOpen: !this.data.summaryOpen })
  },

  onHome: function () {
    wx.navigateBack({
      fail: function () {
        wx.reLaunch({ url: '/pages/index/index' })
      }
    })
  }
})
