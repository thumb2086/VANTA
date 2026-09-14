class_name AudioManager
extends Node

## 播放「工具鏈產生」的音效（assets/sfx/*.wav）與 BGM（assets/bgm/*.wav）。
## 事件 → 音效名稱 對照來自 assets/fx/event_bindings.json（可程式化）。
## BGM：前奏播一次 → 從 loop_start 無縫循環（由 sidecar JSON 提供循環點）。

const MAX_PLAYERS := 10

var _streams := {}
var _players: Array[AudioStreamPlayer] = []
var _event_sfx := {}
var _bgm := AudioStreamPlayer.new()
var _bgm_loop_from := 0.0
var _bgm_tracks := {}            # name -> {path, loop_from}
var _bgm_current := ""
var _synth: SynthWeaponAudio = null


func setup(index: Dictionary, bindings: Dictionary) -> void:
	# 預載所有音效
	for path in index.get("sfx", []):
		var stream: AudioStream = load(path)
		if stream != null:
			var path_s := String(path)
			var name := path_s.get_file().get_basename()
			_streams[name] = stream
	# 事件→音效（數字事件碼 → sfx 名，由 main.gd 對照協定常數）
	var events: Dictionary = bindings.get("events", {})
	_event_sfx = {
		NetClient.EV_SPIKE_PLANTED: "spikeplanted",
		NetClient.EV_SPIKE_DEFUSED: "spikedefused",
		NetClient.EV_SPIKE_DETONATED: "spikeexploded",
		NetClient.EV_ROUND_WIN: "attackerswin",
		NetClient.EV_ROUND_LOSS: "defenderswin",
		NetClient.EV_MATCH_END: "victory"
	}
	# 建立播放池
	for i in range(MAX_PLAYERS):
		var p := AudioStreamPlayer.new()
		p.volume_db = -6.0
		add_child(p)
		_players.append(p)
	# BGM 播放器（前奏後循環）
	add_child(_bgm)
	_bgm.volume_db = -10.0
	_bgm.finished.connect(_on_bgm_finished)
	# 載入 BGM 曲目 + 循環點（sidecar JSON）
	for path in index.get("bgm_meta", []):
		var f := FileAccess.open(path, FileAccess.READ)
		if f == null:
			continue
		var data: Dictionary = JSON.parse_string(f.get_as_text())
		var gname: String = data.get("name", "")
		if gname != "":
			var wav_path := String(path).get_base_dir().path_join(gname + ".wav")
			_bgm_tracks[gname] = {
				"path": wav_path,
				"loop_from": float(data.get("loop_start_sec", 0.0))
			}
	# 合成武器音效引擎
	_synth = SynthWeaponAudio.new()
	add_child(_synth)


func play(name: String, pitch := 1.0, volume := 0.0) -> void:
	var stream: AudioStream = _streams.get(name)
	if stream == null:
		return
	for p in _players:
		if not p.playing:
			p.stream = stream
			p.pitch_scale = pitch
			p.volume_db = volume
			p.play()
			return
	# 全部忙碌 → 覆寫最舊
	_players[0].stream = stream
	_players[0].pitch_scale = pitch
	_players[0].play()


func play_synth(weapon_key: String, pitch := 1.0, volume_db := 0.0, pan := 0.0) -> void:
	"""播放合成武器音效（pan = 聲像 -1左..+1右）。"""
	if _synth != null:
		_synth.trigger(weapon_key, pitch, volume_db, pan)
	else:
		# 後備：MP3
		play(weapon_key + "tap", pitch, volume_db)


func play_event(event_code: int, pitch := 1.0) -> void:
	var name: String = _event_sfx.get(event_code, "")
	if name != "":
		play(name, pitch)


# ── 擊殺連殺音效（1st → 4th → ace）──
var _kill_streak := 0


func play_hitmarker() -> void:
	play("headshot_confirm", 1.8, -4.0)


func play_hitmarker_headshot() -> void:
	play("headshotsound", 1.0, -2.0)


func play_kill() -> void:
	_kill_streak += 1
	match _kill_streak:
		1: play("1stkill", 1.0, -4.0)
		2: play("2ndkill", 1.0, -4.0)
		3: play("3rdkill", 1.0, -4.0)
		4: play("4thkill", 1.0, -4.0)
		_: play("ace", 1.0, -4.0)


func reset_kill_streak() -> void:
	_kill_streak = 0


func play_round_result(win: bool, own_team_attacker: bool) -> void:
	# 我方勝利 → 攻方勝/守方勝 語音；敗北 → 對方勝利語音
	if win:
		play("attackerswin" if own_team_attacker else "defenderswin", 1.0, -2.0)
	else:
		play("defenderswin" if own_team_attacker else "attackerswin", 1.0, -2.0)
		_kill_streak = 0   # 回合結束重置連殺


# --------------------------------------------------------------------- #
# BGM
# --------------------------------------------------------------------- #
func set_bgm(track_name: String) -> void:
	"""切換 BGM（前奏 → 循環段無縫 LOOP_FORWARD）。"""
	if track_name == _bgm_current:
		return
	var track: Dictionary = _bgm_tracks.get(track_name, {})
	if track.is_empty():
		return
	_bgm_current = track_name
	_bgm_loop_from = track["loop_from"]
	var stream: AudioStream = load(track["path"])
	if stream == null:
		return
	# WAV 原生循環：loop_begin=前奏結束取樣點 → 引擎層級無縫，不靠 finished 重播
	if stream is AudioStreamWAV:
		var wav := stream as AudioStreamWAV
		var rate := float(wav.mix_rate)
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = int(_bgm_loop_from * rate)
		wav.loop_end = wav.data.size() / _bytes_per_frame(wav)
	_bgm.stream = stream
	_bgm.play()


func _bytes_per_frame(wav: AudioStreamWAV) -> int:
	var bytes := 2 if wav.format == AudioStreamWAV.FORMAT_16_BITS else 1
	return bytes * (2 if wav.stereo else 1)


func _on_bgm_finished() -> void:
	# 後備：非 WAV 或未設循環時，播完從頭再來
	if _bgm.stream != null and not (_bgm.stream is AudioStreamWAV):
		_bgm.play()
