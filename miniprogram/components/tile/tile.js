var tiles = require('../../utils/tiles')

Component({
  properties: {
    code: { type: String, value: '' },
    selected: { type: Boolean, value: false },
    highlight: { type: Boolean, value: false },
    small: { type: Boolean, value: false },
    faceDown: { type: Boolean, value: false }
  },
  data: {
    src: tiles.tilePath('back')
  },
  observers: {
    'code, faceDown': function (code, faceDown) {
      this.setData({ src: tiles.tilePath(faceDown ? 'back' : code) })
    }
  },
  methods: {
    onTap: function () {
      this.triggerEvent('tap', { code: this.data.code })
    }
  }
})
