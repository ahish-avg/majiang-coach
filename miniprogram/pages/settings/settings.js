var api = require('../../utils/api')

Page({
  data: {
    api_base: '',
    hints_on: false,
    llm_base_url: '',
    llm_api_key: '',
    llm_model: ''
  },
  onShow: function () {
    var s = api.getSettings()
    this.setData({
      api_base: s.api_base || '',
      hints_on: !!s.hints_on,
      llm_base_url: s.llm_base_url || '',
      llm_api_key: s.llm_api_key || '',
      llm_model: s.llm_model || ''
    })
  },
  onInput: function (e) {
    var field = e.currentTarget.dataset.field
    var update = {}
    update[field] = e.detail.value
    this.setData(update)
  },
  onHintsChange: function (e) {
    this.setData({ hints_on: !!e.detail.value })
  },
  onSave: function () {
    var data = this.data
    wx.setStorageSync('settings', {
      api_base: (data.api_base || '').trim(),
      hints_on: !!data.hints_on,
      llm_base_url: (data.llm_base_url || '').trim(),
      llm_api_key: (data.llm_api_key || '').trim(),
      llm_model: (data.llm_model || '').trim()
    })
    wx.showToast({ title: '已保存', icon: 'success' })
    setTimeout(function () {
      wx.navigateBack()
    }, 600)
  }
})
