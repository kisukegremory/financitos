// Trilha de fundo gerativa (Web Audio): drone suave em acorde + "ondas" de ruído filtrado.
// Determinística: a mesma seed (ex.: o título) sempre gera o mesmo som. Custo zero, sem arquivos.

function mulberry32(a) {
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function seedFrom(text) {
  let h = 2166136261
  for (const ch of text) h = Math.imul(h ^ ch.codePointAt(0), 16777619)
  return h >>> 0
}

const ROOTS = [98, 110, 116.54, 130.81, 146.83] // Sol2, Lá2, Lá#2, Dó3, Ré3
const CHORDS = [
  [0, 7, 12, 16], // maior aberto
  [0, 7, 14, 19], // suspenso (add9)
  [0, 5, 12, 17], // quartas
  [0, 7, 15, 19], // menor aberto
]

function pinkNoise(ctx, rand, seconds = 6) {
  const len = ctx.sampleRate * seconds
  const buf = ctx.createBuffer(1, len, ctx.sampleRate)
  const data = buf.getChannelData(0)
  let b0 = 0, b1 = 0, b2 = 0
  for (let i = 0; i < len; i++) {
    const w = rand() * 2 - 1
    b0 = 0.99765 * b0 + w * 0.099046
    b1 = 0.963 * b1 + w * 0.2965164
    b2 = 0.57 * b2 + w * 1.0526913
    data[i] = (b0 + b1 + b2 + w * 0.1848) * 0.06
  }
  return buf
}

export function createAmbient(ctx, seed) {
  const rand = mulberry32(seed)
  const pick = (arr) => arr[Math.floor(rand() * arr.length)]
  const sources = []

  const output = ctx.createGain()
  output.gain.value = 0

  // drone: cada nota com dois osciladores levemente desafinados, "respirando" devagar
  const tone = ctx.createBiquadFilter()
  tone.type = 'lowpass'
  tone.frequency.value = 800
  tone.Q.value = 0.4
  const sweep = ctx.createOscillator()
  sweep.frequency.value = 0.02 + rand() * 0.03
  const sweepDepth = ctx.createGain()
  sweepDepth.gain.value = 350
  sweep.connect(sweepDepth).connect(tone.frequency)
  sources.push(sweep)

  const root = pick(ROOTS)
  for (const semis of pick(CHORDS)) {
    const voice = ctx.createGain()
    voice.gain.value = 0.045
    const swell = ctx.createOscillator()
    swell.frequency.value = 0.04 + rand() * 0.07
    const swellDepth = ctx.createGain()
    swellDepth.gain.value = 0.03
    swell.connect(swellDepth).connect(voice.gain)
    sources.push(swell)
    for (const detune of [-5, 5]) {
      const osc = ctx.createOscillator()
      osc.type = rand() < 0.6 ? 'sine' : 'triangle'
      osc.frequency.value = root * 2 ** (semis / 12)
      osc.detune.value = detune + (rand() - 0.5) * 4
      osc.connect(voice)
      sources.push(osc)
    }
    voice.connect(tone)
  }

  // eco longo para dar espaço
  const delay = ctx.createDelay(2)
  delay.delayTime.value = 0.45 + rand() * 0.3
  const feedback = ctx.createGain()
  feedback.gain.value = 0.45
  const damp = ctx.createBiquadFilter()
  damp.type = 'lowpass'
  damp.frequency.value = 1200
  tone.connect(output)
  tone.connect(delay)
  delay.connect(damp).connect(feedback).connect(delay)
  damp.connect(output)

  // ondas: ruído rosa abafado, subindo e descendo a cada ~12 s
  const noise = ctx.createBufferSource()
  noise.buffer = pinkNoise(ctx, rand)
  noise.loop = true
  const muffle = ctx.createBiquadFilter()
  muffle.type = 'lowpass'
  muffle.frequency.value = 500
  const waves = ctx.createGain()
  waves.gain.value = 0.12
  const tide = ctx.createOscillator()
  tide.frequency.value = 0.06 + rand() * 0.04
  const tideDepth = ctx.createGain()
  tideDepth.gain.value = 0.1
  tide.connect(tideDepth).connect(waves.gain)
  noise.connect(muffle).connect(waves).connect(output)
  sources.push(noise, tide)

  return {
    output,
    start(at, fadeIn = 5) {
      for (const s of sources) s.start(at)
      output.gain.setValueAtTime(0, at)
      output.gain.linearRampToValueAtTime(1, at + fadeIn)
    },
    fadeOut(at, duration = 6) {
      output.gain.setValueAtTime(1, at)
      output.gain.linearRampToValueAtTime(0, at + duration)
    },
  }
}

// Trilha a partir de uma música pronta (Lyria): mesmo contrato do createAmbient
export function createTrackBed(ctx, buffer, level = 0.45) {
  const output = ctx.createGain()
  output.gain.value = 0
  const src = ctx.createBufferSource()
  src.buffer = buffer
  src.loop = true
  src.connect(output)
  return {
    output,
    start(at, fadeIn = 5) {
      src.start(at)
      output.gain.setValueAtTime(0, at)
      output.gain.linearRampToValueAtTime(level, at + fadeIn)
    },
    fadeOut(at, duration = 6) {
      output.gain.setValueAtTime(level, at)
      output.gain.linearRampToValueAtTime(0, at + duration)
    },
  }
}
