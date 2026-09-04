var api = require('../../utils/api')
var viewmap = require('../../utils/viewmap')
var tilesUtil = require('../../utils/tiles')

var KAN_KIND_LABELS = {
  ankan: '暗杠',
  daiminkan: '直杠(大明杠)',
  shouminkan: '补杠'
}

function joinSeats(list) {
  return (list || []).map(function (s) {
    return '座' + s
  }).join(' ')
}

function payText(payerSeats, amountEach) {
  var seats = payerSeats || []
  if (seats.length === 1) {
    return '座' + seats[0] + ' 付 ' + amountEach
  }
  return joinSeats(seats) + ' 各付 ' + amountEach
}

Page({
  data: {
    loading: true,
    loadError: false,
    sid: '',
    strength: 'mid',
    hints: false,
    submitting: false,
    phase: '',
    phaseLabel: '',
    prompt: null,
    view: null,
    drawnCode: '',
    buttons: [],
    lackButtons: [],
    lackMap: viewmap.SUIT_NAMES,
    adv: null,
    selected: [],
    swapReady: false,
    highlightCode: '',
    discardSet: [],
    handTiles: [],
    lastDiscard: null,
    gameOver: false,
    summary: null,
    settle: null,
    settleError: false,
    adviseLoading: false
  },

  onLoad: function (query) {
    query = query || {}
    var strength = query.strength || 'mid'
    var hints = query.hints === '1'
    this.setData({ strength: strength, hints: hints })
    this.startGame()
  },

  onUnload: function () {
    if (this.data.sid) {
      try {
        api.deleteSession(this.data.sid).catch(function () {})
      } catch (e) {}
    }
  },

  startGame: function () {
    var self = this
    var settings = api.getSettings()
    this.setData({
      loading: true,
      loadError: false,
      gameOver: false,
      settle: null,
      settleError: false,
      adv: null,
      selected: [],
      swapReady: false,
      buttons: [],
      lackButtons: [],
      handTiles: []
    })
    api.createSession({
      aiStrengths: [this.data.strength, this.data.strength, this.data.strength],
      hintsOn: this.data.hints,
      llm: api.buildLlm(settings)
    }).then(function (res) {
      self.setData({ sid: res.session_id })
      self.setPrompt(res.prompt)
    }).catch(function () {
      self.setData({ loading: false, loadError: true })
    })
  },

  setPrompt: function (prompt) {
    if (!prompt) return
    var phase = prompt.phase || ''
    var view = prompt.view || null
    var buttons = viewmap.actionButtons(prompt.legal_actions || [])
    var handTiles = []
    var discardSet = []
    var lackButtons = []
    ;(prompt.legal_actions || []).forEach(function (a) {
      if (a.kind === 'discard' && a.tile) discardSet.push(a.tile)
      if (a.kind === 'lack') {
        lackButtons.push({
          key: 'lack_' + a.suit,
          suit: a.suit,
          label: '缺' + (viewmap.SUIT_NAMES[a.suit] || a.suit || ''),
          action: a
        })
      }
    })
    if (view && (phase === 'swap' || phase === 'turn_action')) {
      handTiles = tilesUtil.sortTiles(view.hand || [])
      if (phase === 'turn_action' && prompt.drawn) {
        var idx = handTiles.indexOf(prompt.drawn)
        if (idx !== -1) {
          handTiles.splice(idx, 1)
          handTiles.push(prompt.drawn)
        }
      }
    }
    buttons.forEach(function (b, i) { b.key = b.kind + '_' + i })
    var adv = viewmap.adviseModel(prompt)
    this.setData({
      loading: false,
      loadError: false,
      prompt: prompt,
      phase: phase,
      phaseLabel: viewmap.PHASE_LABELS[phase] || phase,
      view: view,
      drawnCode: prompt.drawn || '',
      highlightCode: prompt.drawn || '',
      buttons: buttons,
      lackButtons: lackButtons,
      adv: adv,
      selected: [],
      swapReady: false,
      discardSet: discardSet,
      handTiles: handTiles,
      lastDiscard: (view && view.last_discard) || null,
      gameOver: !!prompt.game_over,
      summary: prompt.summary || null,
      settle: null,
      settleError: false
    })
    if (prompt.game_over && prompt.record) {
      this.loadSettlement(prompt.record)
    }
  },

  onTileTap: function (e) {
    var code = e.detail.code
    if (!code || code === 'back') return
    if (this.data.phase === 'swap') {
      var sel = this.data.selected.slice()
      var idx = sel.indexOf(code)
      if (idx !== -1) {
        sel.splice(idx, 1)
      } else {
        if (sel.length >= 3) {
          api.toast('最多选 3 张')
          return
        }
        sel.push(code)
      }
      this.setData({ selected: sel, swapReady: viewmap.swapReady(sel) })
      return
    }
    if (this.data.phase === 'turn_action') {
      if (this.data.discardSet.indexOf(code) === -1) {
        api.toast('缺门牌不能打')
        return
      }
      this.submitAction({ kind: 'discard', tile: code })
    }
  },

  onSwapSubmit: function () {
    if (!this.data.swapReady || this.data.submitting) return
    this.submitAction({ kind: 'swap', tiles: this.data.selected.slice() })
  },

  onLack: function (e) {
    if (this.data.submitting) return
    var suit = e.currentTarget.dataset.suit
    this.submitAction({ kind: 'lack', suit: suit })
  },

  onButton: function (e) {
    if (this.data.submitting) return
    var action = e.currentTarget.dataset.action
    if (action) this.submitAction(action)
  },

  submitAction: function (action) {
    var self = this
    if (this.data.submitting) return
    this.setData({ submitting: true })
    api.act(this.data.sid, action).then(function (result) {
      self.setData({ submitting: false })
      self.setPrompt(result)
    }).catch(function () {
      self.setData({ submitting: false })
      if (self.data.sid) {
        api.getSession(self.data.sid).then(function (p) {
          self.setPrompt(p)
        }).catch(function () {})
      }
    })
  },

  onAskCoach: function () {
    var self = this
    if (this.data.adviseLoading || this.data.submitting) return
    this.setData({ adviseLoading: true })
    wx.showLoading({ title: '教练思考中…', mask: true })
    api.advise(this.data.sid).then(function (res) {
      wx.hideLoading()
      self.setData({
        adviseLoading: false,
        adv: viewmap.adviseModel(Object.assign({}, self.data.prompt, { advise: res }))
      })
    }).catch(function () {
      wx.hideLoading()
      self.setData({ adviseLoading: false })
    })
  },

  loadSettlement: function (record) {
    var self = this
    this.setData({ settle: null, settleError: false })
    api.score({ record: record }).then(function (res) {
      self.setData({ settle: self.buildSettle(res), settleError: false })
    }).catch(function () {
      self.setData({ settleError: true })
    })
  },

  buildSettle: function (res) {
    res = res || {}
    var wins = (res.wins || []).map(function (w, i) {
      var fan = w.fan || {}
      var fanItems = (fan.items || []).map(function (it, j) {
        return { key: 'fan' + i + '_' + j, name: it.name, fan: it.fan, basis: it.basis || '' }
      })
      return {
        key: 'win_' + i,
        seat: w.seat,
        by: w.by,
        tile: w.tile,
        fanItems: fanItems,
        totalFan: fan.total_fan,
        multiplier: fan.multiplier,
        capApplied: !!fan.cap_applied,
        pay: payText(w.payer_seats, w.amount_each)
      }
    })
    var kans = (res.kans || []).map(function (k, i) {
      return {
        key: 'kan_' + i,
        seat: k.seat,
        kindLabel: KAN_KIND_LABELS[k.kind] || k.kind,
        tile: k.tile,
        pay: payText(k.payer_seats, k.amount_each)
      }
    })
    var tenpais = (res.tenpais || []).map(function (t, i) {
      return {
        key: 'tenpai_' + i,
        payer: t.payer,
        waitSeat: t.wait_seat,
        waitTiles: t.wait_tiles || [],
        maxFan: t.max_fan,
        multiplier: t.multiplier,
        amount: t.amount
      }
    })
    var huazhus = (res.huazhus || []).map(function (h, i) {
      return {
        key: 'huazhu_' + i,
        huazhuSeat: h.huazhu_seat,
        payee: h.payee,
        amount: h.amount
      }
    })
    var perSeat = []
    var total = 0
    for (var s = 0; s < 4; s++) {
      var v = (res.per_seat || {})[String(s)]
      if (v === undefined || v === null) v = (res.per_seat || {})[s]
      v = v || 0
      total += v
      perSeat.push({
        seat: s,
        value: (v > 0 ? '+' : '') + v,
        pos: v > 0,
        neg: v < 0
      })
    }
    return {
      baseScore: res.base_score,
      drawn: !!res.drawn,
      wins: wins,
      kans: kans,
      tenpais: tenpais,
      huazhus: huazhus,
      perSeat: perSeat,
      total: (total > 0 ? '+' : '') + total
    }
  },

  onRetryScore: function () {
    if (this.data.prompt && this.data.prompt.record) {
      this.loadSettlement(this.data.prompt.record)
    }
  },

  onReview: function () {
    var app = getApp()
    if (app) {
      app.globalData = app.globalData || {}
      app.globalData.reviewPayload = {
        record: this.data.prompt.record,
        seed: this.data.summary ? this.data.summary.seed : undefined
      }
    }
    wx.navigateTo({ url: '/pages/review/review?from=practice' })
  },

  onGoHome: function () {
    wx.reLaunch({ url: '/pages/index/index' })
  },

  onNewGame: function () {
    if (this.data.sid) {
      try {
        api.deleteSession(this.data.sid).catch(function () {})
      } catch (e) {}
    }
    this.setData({ sid: '' })
    this.startGame()
  },

  onRetryLoad: function () {
    this.startGame()
  }
})
