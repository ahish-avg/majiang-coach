Page({
  data: {
    strengths: [
      { key: 'weak', label: '弱' },
      { key: 'mid', label: '中' },
      { key: 'strong', label: '强' }
    ],
    strength: 'mid',
    hintsOn: false,
    seed: ''
  },
  onLoad: function () {
    var api = require('../../utils/api')
    var settings = api.getSettings()
    this.setData({ hintsOn: !!settings.hints_on })
  },
  onPickStrength: function (e) {
    this.setData({ strength: e.currentTarget.dataset.key })
  },
  onHintsChange: function (e) {
    this.setData({ hintsOn: !!e.detail.value })
  },
  onSeedInput: function (e) {
    this.setData({ seed: e.detail.value })
  },
  onStartPractice: function () {
    var s = this.data.strength
    var hints = this.data.hintsOn ? 1 : 0
    wx.navigateTo({
      url: '/pages/practice/practice?strength=' + s + '&hints=' + hints
    })
  },
  onReview: function () {
    var seed = (this.data.seed || '').trim()
    if (!seed) {
      wx.showToast({ title: '请输入种子号', icon: 'none' })
      return
    }
    wx.navigateTo({
      url: '/pages/review/review?seed=' + encodeURIComponent(seed)
    })
  },
  onSettings: function () {
    wx.navigateTo({ url: '/pages/settings/settings' })
  }
})
