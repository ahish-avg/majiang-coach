var viewmap = require('../../utils/viewmap')

Component({
  properties: {
    melds: { type: Array, value: [] }
  },
  data: {
    groups: []
  },
  observers: {
    'melds': function (melds) {
      var groups = (melds || []).map(function (meld, i) {
        var tiles = viewmap.meldTiles(meld).map(function (code, j) {
          return { key: i + '_' + j + '_' + code, code: code }
        })
        return {
          key: 'g' + i,
          label: viewmap.meldLabel(meld),
          tiles: tiles
        }
      })
      this.setData({ groups: groups })
    }
  }
})
