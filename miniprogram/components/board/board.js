var viewmap = require('../../utils/viewmap')

Component({
  options: {
    multipleSlots: true
  },
  properties: {
    view: { type: Object, value: null },
    drawnCode: { type: String, value: '' }
  },
  data: {
    m: null
  },
  observers: {
    'view, drawnCode': function (view, drawnCode) {
      this.setData({
        m: view ? viewmap.boardModel(view, drawnCode || '') : null
      })
    }
  }
})
