Component({
  properties: {
    tiles: { type: Array, value: [] },
    selected: { type: Array, value: [] },
    highlightCode: { type: String, value: '' },
    interactive: { type: Boolean, value: false },
    faceDown: { type: Boolean, value: false },
    small: { type: Boolean, value: false }
  },
  data: {
    items: []
  },
  observers: {
    'tiles, selected, highlightCode, faceDown, small': function (tilesArr, selectedArr, hl, down, small) {
      var list = (tilesArr || []).map(function (code, i) {
        return {
          key: code + '_' + i,
          code: code,
          selected: (selectedArr || []).indexOf(code) !== -1,
          highlight: code === hl && !!hl,
          faceDown: !!down || code === 'back',
          small: !!small
        }
      })
      this.setData({ items: list })
    }
  },
  methods: {
    onTileTap: function (e) {
      if (!this.data.interactive) return
      this.triggerEvent('tiletap', { code: e.detail.code })
    }
  }
})
