class_name SynthWeaponAudio
extends Node

## 合成武器音效引擎（AudioStreamGenerator）。
## 用振盪器 + 包絡 + 失真產生即時槍聲，取代 MP3 檔案。
## 每把槍有獨立參數（振盪器層、包絡、失真度、音高掃描）。

const MAX_VOICES := 12
const MIX_RATE := 24000  # 低取樣率節省 CPU（短促槍聲足夠）

# ── 振盪器類型 ──
const OSC_NOISE := 0
const OSC_SINE := 1
const OSC_SAW := 2
const OSC_SQUARE := 3

# ── 武器合成參數 ──
# layers: 每層 {type, freq, freq_lo, freq_hi, amp, attack_ms, decay_ms, pitch_sweep, distortion}
var WEAPON_PATCHES := {
	"vandal": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 200, "freq_hi": 2200, "amp": 0.7, "attack_ms": 0.5, "decay_ms": 40, "distortion": 0.5},
			{"type": OSC_SAW, "freq": 110, "amp": 0.45, "attack_ms": 0.5, "decay_ms": 35, "pitch_sweep": -80},
			{"type": OSC_SINE, "freq": 55, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 30},
		],
		"pitch_jitter": 0.08, "volume_db": -8.0,
	},
	"phantom": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 300, "freq_hi": 3000, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 30, "distortion": 0.3},
			{"type": OSC_SINE, "freq": 180, "amp": 0.35, "attack_ms": 0.5, "decay_ms": 25},
			{"type": OSC_NOISE, "freq_lo": 1000, "freq_hi": 6000, "amp": 0.2, "attack_ms": 0.3, "decay_ms": 15, "distortion": 0.1},
		],
		"pitch_jitter": 0.1, "volume_db": -10.0,
	},
	"classic": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 400, "freq_hi": 2500, "amp": 0.55, "attack_ms": 0.5, "decay_ms": 20, "distortion": 0.25},
			{"type": OSC_SINE, "freq": 200, "amp": 0.3, "attack_ms": 0.5, "decay_ms": 15},
		],
		"pitch_jitter": 0.12, "volume_db": -10.0,
	},
	"ghost": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 500, "freq_hi": 3500, "amp": 0.4, "attack_ms": 0.3, "decay_ms": 18, "distortion": 0.15},
			{"type": OSC_SINE, "freq": 250, "amp": 0.3, "attack_ms": 0.3, "decay_ms": 15},
		],
		"pitch_jitter": 0.12, "volume_db": -12.0,
	},
	"frenzy": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 350, "freq_hi": 2800, "amp": 0.5, "attack_ms": 0.4, "decay_ms": 15, "distortion": 0.35},
			{"type": OSC_SAW, "freq": 300, "amp": 0.3, "attack_ms": 0.3, "decay_ms": 12, "pitch_sweep": -120},
		],
		"pitch_jitter": 0.15, "volume_db": -10.0,
	},
	"bandit": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 200, "freq_hi": 2000, "amp": 0.65, "attack_ms": 0.5, "decay_ms": 35, "distortion": 0.4},
			{"type": OSC_SAW, "freq": 140, "amp": 0.4, "attack_ms": 0.5, "decay_ms": 30, "pitch_sweep": -70},
			{"type": OSC_SINE, "freq": 70, "amp": 0.45, "attack_ms": 0.5, "decay_ms": 25},
		],
		"pitch_jitter": 0.07, "volume_db": -7.0,
	},
	"sheriff": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 150, "freq_hi": 1800, "amp": 0.8, "attack_ms": 0.5, "decay_ms": 55, "distortion": 0.6},
			{"type": OSC_SAW, "freq": 80, "amp": 0.55, "attack_ms": 0.5, "decay_ms": 50, "pitch_sweep": -60},
			{"type": OSC_SINE, "freq": 40, "amp": 0.6, "attack_ms": 0.5, "decay_ms": 45},
		],
		"pitch_jitter": 0.05, "volume_db": -6.0,
	},
	"stinger": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 400, "freq_hi": 3200, "amp": 0.45, "attack_ms": 0.4, "decay_ms": 18, "distortion": 0.3},
			{"type": OSC_SAW, "freq": 350, "amp": 0.25, "attack_ms": 0.3, "decay_ms": 14, "pitch_sweep": -100},
		],
		"pitch_jitter": 0.12, "volume_db": -10.0,
	},
	"spectre": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 350, "freq_hi": 2800, "amp": 0.5, "attack_ms": 0.4, "decay_ms": 22, "distortion": 0.25},
			{"type": OSC_SAW, "freq": 220, "amp": 0.3, "attack_ms": 0.4, "decay_ms": 18, "pitch_sweep": -80},
			{"type": OSC_SINE, "freq": 110, "amp": 0.35, "attack_ms": 0.4, "decay_ms": 16},
		],
		"pitch_jitter": 0.1, "volume_db": -8.0,
	},
	"bulldog": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 250, "freq_hi": 2000, "amp": 0.6, "attack_ms": 0.5, "decay_ms": 30, "distortion": 0.4},
			{"type": OSC_SAW, "freq": 160, "amp": 0.4, "attack_ms": 0.5, "decay_ms": 28, "pitch_sweep": -60},
		],
		"pitch_jitter": 0.08, "volume_db": -8.0,
	},
	"guardian": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 180, "freq_hi": 1600, "amp": 0.7, "attack_ms": 0.5, "decay_ms": 50, "distortion": 0.45},
			{"type": OSC_SAW, "freq": 90, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 45, "pitch_sweep": -50},
			{"type": OSC_SINE, "freq": 45, "amp": 0.55, "attack_ms": 0.5, "decay_ms": 40},
		],
		"pitch_jitter": 0.06, "volume_db": -6.0,
	},
	"marshal": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 120, "freq_hi": 1200, "amp": 0.75, "attack_ms": 0.5, "decay_ms": 60, "distortion": 0.5},
			{"type": OSC_SAW, "freq": 70, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 55, "pitch_sweep": -40},
			{"type": OSC_SINE, "freq": 35, "amp": 0.6, "attack_ms": 0.5, "decay_ms": 50},
		],
		"pitch_jitter": 0.04, "volume_db": -4.0,
	},
	"operator": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 80, "freq_hi": 800, "amp": 0.9, "attack_ms": 0.5, "decay_ms": 80, "distortion": 0.7},
			{"type": OSC_SAW, "freq": 50, "amp": 0.6, "attack_ms": 0.5, "decay_ms": 70, "pitch_sweep": -30},
			{"type": OSC_SINE, "freq": 25, "amp": 0.7, "attack_ms": 0.5, "decay_ms": 65},
		],
		"pitch_jitter": 0.03, "volume_db": -2.0,
	},
	"outlaw": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 100, "freq_hi": 1000, "amp": 0.82, "attack_ms": 0.5, "decay_ms": 65, "distortion": 0.6},
			{"type": OSC_SAW, "freq": 60, "amp": 0.55, "attack_ms": 0.5, "decay_ms": 58, "pitch_sweep": -35},
			{"type": OSC_SINE, "freq": 30, "amp": 0.6, "attack_ms": 0.5, "decay_ms": 52},
		],
		"pitch_jitter": 0.04, "volume_db": -3.0,
	},
	"bucky": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 100, "freq_hi": 1500, "amp": 0.85, "attack_ms": 0.5, "decay_ms": 70, "distortion": 0.65},
			{"type": OSC_SAW, "freq": 60, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 60, "pitch_sweep": -50},
			{"type": OSC_SINE, "freq": 30, "amp": 0.65, "attack_ms": 0.5, "decay_ms": 55},
		],
		"pitch_jitter": 0.04, "volume_db": -4.0,
	},
	"judge": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 100, "freq_hi": 1400, "amp": 0.9, "attack_ms": 0.5, "decay_ms": 65, "distortion": 0.7},
			{"type": OSC_SAW, "freq": 55, "amp": 0.55, "attack_ms": 0.5, "decay_ms": 55, "pitch_sweep": -45},
			{"type": OSC_SINE, "freq": 28, "amp": 0.65, "attack_ms": 0.5, "decay_ms": 50},
		],
		"pitch_jitter": 0.04, "volume_db": -3.0,
	},
	"ares": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 180, "freq_hi": 1800, "amp": 0.65, "attack_ms": 0.5, "decay_ms": 45, "distortion": 0.45},
			{"type": OSC_SAW, "freq": 100, "amp": 0.45, "attack_ms": 0.5, "decay_ms": 40, "pitch_sweep": -70},
			{"type": OSC_SINE, "freq": 50, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 35},
		],
		"pitch_jitter": 0.06, "volume_db": -6.0,
	},
	"odin": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 150, "freq_hi": 1500, "amp": 0.75, "attack_ms": 0.5, "decay_ms": 55, "distortion": 0.55},
			{"type": OSC_SAW, "freq": 80, "amp": 0.5, "attack_ms": 0.5, "decay_ms": 50, "pitch_sweep": -60},
			{"type": OSC_SINE, "freq": 40, "amp": 0.55, "attack_ms": 0.5, "decay_ms": 45},
		],
		"pitch_jitter": 0.05, "volume_db": -5.0,
	},
	"knife": {
		"layers": [
			{"type": OSC_NOISE, "freq_lo": 800, "freq_hi": 5000, "amp": 0.4, "attack_ms": 0.3, "decay_ms": 25, "distortion": 0.2},
			{"type": OSC_SINE, "freq": 1200, "amp": 0.3, "attack_ms": 0.2, "decay_ms": 20, "pitch_sweep": -400},
		],
		"pitch_jitter": 0.15, "volume_db": -12.0,
	},
}

# ── 活躍聲音物件池 ──
var _voices: Array[Dictionary] = []
var _player: AudioStreamPlayer = null
var _gen: AudioStreamGenerator = null


func _ready() -> void:
	_gen = AudioStreamGenerator.new()
	_gen.mix_rate = MIX_RATE
	_gen.buffer_length = 0.15  # 150ms buffer（短槍聲綽綽有餘）
	_player = AudioStreamPlayer.new()
	_player.stream = _gen
	_player.volume_db = 0.0
	add_child(_player)
	_player.play()
	# 預建 voice 物件池
	for i in range(MAX_VOICES):
		_voices.append({
			"active": false,
			"patch": {},
			"t": 0.0,           # 當前時間（秒）
			"duration": 0.0,    # 總持續時間
			"pitch_mult": 1.0,
			"vol": 0.0,
			"pan": 0.0,         # -1 左 .. +1 右
			"osc_phases": [],   # 每層振盪器相位
			"env": [],          # 每層包絡值
			"lp": [],           # 每層低通狀態（noise 用）
			"hp": [],           # 每層高通狀態（noise 用）
		})


func trigger(weapon_key: String, pitch := 1.0, volume_db := 0.0, pan := 0.0) -> void:
	"""觸發一個合成槍聲。weapon_key = "vandal"/"phantom" 等；pan = 聲像。"""
	var patch: Dictionary = WEAPON_PATCHES.get(weapon_key, WEAPON_PATCHES.get("vandal"))
	# 找空閒 voice
	var voice: Dictionary = {}
	for v in _voices:
		if not v["active"]:
			voice = v
			break
	if voice.is_empty():
		# 覆寫最舊
		voice = _voices[0]
	# 計算隨機音高偏移
	var jitter: float = patch.get("pitch_jitter", 0.08)
	var pitch_mult := pitch * randf_range(1.0 - jitter, 1.0 + jitter)
	var vol: float = patch.get("volume_db", -8.0) + volume_db
	var layers: Array = patch.get("layers", [])
	var max_dur := 0.0
	for layer in layers:
		var dur: float = (layer.get("attack_ms", 0.5) + layer.get("decay_ms", 30)) / 1000.0
		if dur > max_dur:
			max_dur = dur
	voice["active"] = true
	voice["patch"] = patch
	voice["t"] = 0.0
	voice["duration"] = max_dur * 1.5  # 留一點尾巴
	voice["pitch_mult"] = pitch_mult
	voice["vol"] = vol
	voice["pan"] = clampf(pan, -1.0, 1.0)
	voice["osc_phases"] = []
	voice["env"] = []
	voice["lp"] = []
	voice["hp"] = []
	for layer in layers:
		voice["osc_phases"].append(randf() * TAU)  # 隨機起始相位
		voice["env"].append(0.0)
		voice["lp"].append(0.0)
		voice["hp"].append(0.0)


func _process(_delta: float) -> void:
	if _player == null or _gen == null:
		return
	var playback: AudioStreamGeneratorPlayback = _player.get_stream_playback()
	if playback == null:
		return
	var frames_avail: int = playback.get_frames_available()
	var mix_rate_f: float = float(MIX_RATE)
	for _i in range(frames_avail):
		var sample := Vector2.ZERO
		for v in _voices:
			if not v["active"]:
				continue
			sample += _render_voice(v, 1.0 / mix_rate_f)
		# 軟限幅防削波
		sample.x = tanh(sample.x * 1.5)
		sample.y = tanh(sample.y * 1.5)
		playback.push_frame(sample)


func _render_voice(v: Dictionary, dt: float) -> Vector2:
	"""渲染一個 voice 的當前取樣（單聲道 → 立體聲）。"""
	var t: float = v["t"]
	var layers: Array = v["patch"].get("layers", [])
	var vol_db: float = v["vol"]
	var gain := pow(10.0, vol_db / 20.0)
	var out := 0.0
	for i in range(layers.size()):
		var layer: Dictionary = layers[i]
		var osc_type: int = layer.get("type", OSC_NOISE)
		var freq: float = layer.get("freq", 440.0)
		var freq_lo: float = layer.get("freq_lo", 200.0)
		var freq_hi: float = layer.get("freq_hi", 2000.0)
		var amp: float = layer.get("amp", 0.5)
		var attack_s: float = layer.get("attack_ms", 0.5) / 1000.0
		var decay_s: float = layer.get("decay_ms", 30) / 1000.0
		var sweep: float = layer.get("pitch_sweep", 0.0)
		var dist: float = layer.get("distortion", 0.0)
		# 包絡
		var env: float = v["env"][i]
		if t < attack_s:
			env = t / attack_s if attack_s > 0.0 else 1.0
		else:
			var decay_t: float = t - attack_s
			env = exp(-decay_t / (decay_s * 0.3)) if decay_s > 0.0 else 0.0
		v["env"][i] = env
		# 振盪器
		var phase: float = v["osc_phases"][i]
		var current_freq: float = freq
		if sweep != 0.0 and decay_s > 0.0:
			var decay_t2: float = t - attack_s
			var sweep_u: float = clampf(decay_t2 / decay_s, 0.0, 1.0)
			current_freq = freq + sweep * (1.0 - sweep_u)
		# 對 noise 類型：白噪 → 低通(freq_hi) → 高通(freq_lo) → 帶通槍聲質感
		var osc_val := 0.0
		match osc_type:
			OSC_NOISE:
				var n := randf_range(-1.0, 1.0)
				# one-pole 低通 @ freq_hi（去除「嘶嘶」高頻）
				var k_lp := 1.0 - exp(-TAU * freq_hi / float(MIX_RATE))
				v["lp"][i] += k_lp * (n - v["lp"][i])
				var lpd := v["lp"][i]
				# one-pole 高通 @ freq_lo（去除轟隆低頻）
				var k_hp := 1.0 - exp(-TAU * freq_lo / float(MIX_RATE))
				v["hp"][i] += k_hp * (lpd - v["hp"][i])
				osc_val = (lpd - v["hp"][i]) * amp
			OSC_SINE:
				osc_val = sin(phase) * amp
				phase += current_freq * dt * TAU
			OSC_SAW:
				osc_val = (fmod(phase / TAU, 2.0) - 1.0) * amp
				phase += current_freq * dt * TAU
			OSC_SQUARE:
				osc_val = sign(sin(phase)) * amp
				phase += current_freq * dt * TAU
		v["osc_phases"][i] = phase
		# 失真
		if dist > 0.0:
			osc_val = tanh(osc_val * (1.0 + dist * 4.0))
		out += osc_val * env
	v["t"] += dt
	if v["t"] >= v["duration"]:
		v["active"] = false
	# 聲像定位（等冪混合）+ 微空間感
	var pan: float = v.get("pan", 0.0)
	var l_gain := sqrt(0.5 * (1.0 - pan))
	var r_gain := sqrt(0.5 * (1.0 + pan))
	return Vector2(out * l_gain, out * r_gain)
