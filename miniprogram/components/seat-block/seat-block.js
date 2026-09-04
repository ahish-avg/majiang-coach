var viewmap = require('../../utils/viewmap')

Component({
  properties: {
    model: { type: Object, value: null },
    compact: { type: Boolean, value: false }
  },
  data: {
    seatLabel: '',
    lackText: '',
    river: []
  },
  observers: {
    'model': function (model) {
      if (!model) {
        this.setData({ seatLabel: '', lackText: '', river: [] })
        return
      }
      var lackText = model.lackSuit
        ? '缺' + (viewmap.SUIT_NAMES[model.lackSuit] || model.lackSuit)
        : ''
      var river = (model.discards || []).map(function (code, i) {
        return {
          key: 'r' + i + '_' + code,
          code: code,
          highlight: !!model.lastDiscard && code === model.lastDiscard && i === (model.discards || []).length - 1
        }
      })
      this.setData({
        seatLabel: viewmap.seatLabel(model.seat),
        lackText: lackText,
        river: river
      })
    }
  }
})
