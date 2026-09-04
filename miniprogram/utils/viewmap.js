var tiles = require('./tiles')
var SUIT_NAMES = tiles.SUIT_NAMES
var sortTiles = tiles.sortTiles

function seatLabel(seat) {
  return seat === 0 ? '我（座0）' : '座' + seat
}

var PHASE_LABELS = {
  swap: '换三张',
  lack: '定缺',
  turn_action: '摸打',
  claim: '申索',
  robbery: '抢杠',
  game_over: '终局'
}

var ACTION_LABELS = {
  discard: '打出',
  tsumo: '自摸',
  ankan: '暗杠',
  shouminkan: '补杠',
  ron: '胡',
  pon: '碰',
  daiminkan: '大明杠',
  ronkan: '抢杠胡',
  pass: '过',
  swap: '换三张',
  lack: '定缺'
}

var MELD_LABELS = {
  pon: '碰',
  ankan: '暗杠',
  daiminkan: '大明杠',
  shouminkan: '补杠'
}

function meldTiles(meld) {
  if (!meld || !meld.kind) return []
  var tile = meld.tile || 'back'
  if (meld.kind === 'pon') return [tile, tile, tile]
  if (meld.kind === 'ankan') return ['back', 'back', 'back', 'back']
  if (meld.kind === 'shouminkan' || meld.kind === 'daiminkan') return [tile, tile, tile, tile]
  return [tile]
}

function meldLabel(meld) {
  if (!meld || !meld.kind) return ''
  var label = MELD_LABELS[meld.kind] || meld.kind
  if (meld.from !== null && meld.from !== undefined) {
    label += '(座' + meld.from + ')'
  }
  return label
}

function opponentBackCount(publicMeldsForSeat) {
  var melds = publicMeldsForSeat || []
  return Math.max(0, 13 - 3 * melds.length)
}

function includes(arr, v) {
  return (arr || []).indexOf(v) !== -1
}

function seatModel(view, seat, isSelf, drawnCode) {
  view = view || {}
  var publicMelds = (view.public_melds && view.public_melds[seat]) || []
  var discards = (view.discards && view.discards[seat]) || []
  var activeSeats = view.active_seats || []
  var winners = view.winners || []

  var tileCodes
  if (isSelf) {
    var sorted = sortTiles(view.hand || [])
    if (drawnCode) {
      var idx = sorted.indexOf(drawnCode)
      if (idx !== -1) {
        sorted.splice(idx, 1)
        sorted.push(drawnCode)
      }
    }
    tileCodes = sorted
  } else {
    tileCodes = []
    for (var i = 0; i < opponentBackCount(publicMelds); i++) tileCodes.push('back')
  }

  var lastDiscard = null
  if (view.last_discard && view.last_discard.src === seat) {
    lastDiscard = view.last_discard.tile
  }

  return {
    seat: seat,
    isSelf: !!isSelf,
    faceUp: !!isSelf,
    tiles: tileCodes.slice(),
    tileCodes: tileCodes,
    drawnCode: isSelf ? (drawnCode || '') : '',
    melds: publicMelds,
    discards: discards,
    lackSuit: (view.lack_suits && view.lack_suits[seat]) || null,
    active: includes(activeSeats, seat),
    winner: includes(winners, seat),
    lastDiscard: lastDiscard
  }
}

function boardModel(view, drawnCode) {
  view = view || {}
  var self = view.seat || 0
  var positions = {
    bottom: self,
    top: (self + 1) % 4,
    right: (self + 2) % 4,
    left: (self + 3) % 4
  }
  var seats = {}
  var pos
  for (pos in positions) {
    var s = positions[pos]
    var model = seatModel(view, s, s === self, drawnCode)
    model.position = pos
    seats[pos] = model
  }
  return {
    selfSeat: self,
    wallRemaining: view.wall_remaining || 0,
    lastDiscard: view.last_discard || null,
    seats: seats
  }
}

function tileSuffix(tile) {
  return tile ? ' ' + tile : ''
}

function actionButtons(legalActions) {
  var buttons = []
  var passBtn = null
  ;(legalActions || []).forEach(function (a) {
    if (!a || !a.kind) return
    if (a.kind === 'discard') return
    if (a.kind === 'swap') return
    var label
    var action = JSON.parse(JSON.stringify(a))
    switch (a.kind) {
      case 'lack':
        label = '定缺 ' + (SUIT_NAMES[a.suit] || a.suit || '')
        break
      case 'tsumo':
        label = ACTION_LABELS.tsumo + tileSuffix(a.tile)
        break
      case 'ankan':
        label = ACTION_LABELS.ankan + tileSuffix(a.tile)
        break
      case 'shouminkan':
        label = ACTION_LABELS.shouminkan + tileSuffix(a.tile)
        break
      case 'ron':
        label = ACTION_LABELS.ron + tileSuffix(a.tile)
        break
      case 'pon':
        label = ACTION_LABELS.pon + tileSuffix(a.tile)
        break
      case 'daiminkan':
        label = ACTION_LABELS.daiminkan + tileSuffix(a.tile)
        break
      case 'ronkan':
        label = ACTION_LABELS.ronkan + tileSuffix(a.tile)
        break
      case 'pass':
        label = ACTION_LABELS.pass
        break
      default:
        label = ACTION_LABELS[a.kind] || a.kind
    }
    var btn = { label: label, kind: a.kind, action: action }
    if (a.kind === 'pass') {
      passBtn = btn
    } else {
      buttons.push(btn)
    }
  })
  if (passBtn) buttons.push(passBtn)
  return buttons
}

function swapReady(selectedCodes) {
  var sel = selectedCodes || []
  if (sel.length !== 3) return false
  var suit = tiles.suitOf(sel[0])
  if (!suit) return false
  for (var i = 1; i < sel.length; i++) {
    if (tiles.suitOf(sel[i]) !== suit) return false
  }
  return true
}

function hardFromAnalysis(analysis) {
  if (!analysis) return null
  var rec = analysis.recommend
  if (rec) {
    return {
      code: rec.code || '',
      shanten_after: rec.shanten_after,
      is_tenpai_after: !!rec.is_tenpai_after,
      ukeire_count: rec.ukeire_count,
      composite_score: rec.composite_score,
      danger: rec.danger
    }
  }
  var hand = analysis.hand || {}
  if (hand && (hand.shanten !== undefined || hand.shanten_after !== undefined)) {
    return {
      code: '',
      shanten_after: hand.shanten_after !== undefined ? hand.shanten_after : hand.shanten,
      is_tenpai_after: !!hand.is_tenpai,
      ukeire_count: hand.ukeire_count,
      composite_score: hand.composite_score,
      danger: null
    }
  }
  return null
}

function adviseModel(prompt) {
  prompt = prompt || {}
  var advise = prompt.advise || null
  var hint = prompt.hint || null

  var analysis = (advise && advise.analysis) || hint || null
  var llmBlock = null
  var modelUsed = null
  var error = null
  var hasLlm = false

  if (advise) {
    modelUsed = advise.model_used || null
    error = advise.error || null
    if (advise.advice) {
      hasLlm = true
      llmBlock = {
        recommended_tile: advise.advice.recommended_tile || '',
        offense_reason: advise.advice.offense_reason || '',
        defense_reason: advise.advice.defense_reason || '',
        teaching_point: advise.advice.teaching_point || '',
        opponent_read: advise.advice.opponent_read || ''
      }
    }
  }

  var hard = hardFromAnalysis(analysis)
  var recommendCode = ''
  if (llmBlock && llmBlock.recommended_tile) {
    recommendCode = llmBlock.recommended_tile
  } else if (hard && hard.code) {
    recommendCode = hard.code
  }

  return {
    hasLlm: hasLlm,
    modelUsed: modelUsed,
    recommendCode: recommendCode,
    llm: llmBlock,
    hard: hard,
    error: error
  }
}

module.exports = {
  SUIT_NAMES: SUIT_NAMES,
  seatLabel: seatLabel,
  PHASE_LABELS: PHASE_LABELS,
  ACTION_LABELS: ACTION_LABELS,
  meldTiles: meldTiles,
  meldLabel: meldLabel,
  opponentBackCount: opponentBackCount,
  seatModel: seatModel,
  boardModel: boardModel,
  actionButtons: actionButtons,
  swapReady: swapReady,
  adviseModel: adviseModel
}
