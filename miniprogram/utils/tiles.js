var SUIT_CODES = ['m', 's', 'p']

var TILE_PATH = {}
SUIT_CODES.forEach(function (suit) {
  for (var n = 1; n <= 9; n++) {
    TILE_PATH[n + suit] = '/assets/tiles/' + n + suit + '.svg'
  }
})
TILE_PATH.back = '/assets/tiles/back.svg'

var SUIT_NAMES = { m: '万', s: '条', p: '筒' }

function tilePath(code) {
  if (!code || code === 'back' || !TILE_PATH[code]) {
    return TILE_PATH.back
  }
  return TILE_PATH[code]
}

function suitOf(code) {
  if (!code || code === 'back' || code.length < 2) return null
  var suit = code.charAt(code.length - 1)
  return SUIT_NAMES[suit] ? suit : null
}

function numOf(code) {
  if (!code || code === 'back' || code.length < 2) return 0
  var n = parseInt(code.slice(0, code.length - 1), 10)
  return isNaN(n) ? 0 : n
}

var SUIT_ORDER = { m: 0, s: 1, p: 2 }

function sortTiles(codes) {
  var list = (codes || []).slice()
  list.sort(function (a, b) {
    var sa = SUIT_ORDER[suitOf(a)]
    var sb = SUIT_ORDER[suitOf(b)]
    if (sa !== sb) return sa - sb
    return numOf(a) - numOf(b)
  })
  return list
}

module.exports = {
  TILE_PATH: TILE_PATH,
  SUIT_NAMES: SUIT_NAMES,
  tilePath: tilePath,
  suitOf: suitOf,
  numOf: numOf,
  sortTiles: sortTiles
}
