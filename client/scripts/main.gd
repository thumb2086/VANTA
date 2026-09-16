extends Node3D

## VANTA 客戶端主迴圈：
##   鍵盤/滑鼠 → 淨輸入 → (客戶端預測) → UDP → 權威伺服器
##   快照 → 渲染插值 + 伺服器和解
##   遊戲事件 → 音效 / 擊殺特效 / HUD / 連殺宣告
## 地圖/武器/音效/粒子特效全部來自「工具鏈產生的 assets/」。

const DT := 1.0 / 128.0
const EYE_HEIGHT := 1.6
const CROUCH_EYE := 1.25

var net: NetClient = null
var hud: HUD = null
var audio_mgr: AudioManager = null
var vfx_mgr: VFXManager = null
var world_render: RenderWorld = null
var gallery: AgentGallery = null
var cam: Camera3D = null
var viewmodel: WeaponViewmodelV2 = null
var fx2: FxManager = null
var screen_fx: ScreenFx = null
var skin_reg: SkinRegistry = null
var skin_prog: SkinProgression = null
var _skin_res: Dictionary = {}
var _skin_rev := -1
var local := LocalMovement.new()

var asset_index := {}
var _map_data := {}
var _acc := 0.0
var _jump_held := false
var _yaw := 0.0
var _pitch := 0.0
var _sens := 0.0035  # 從 VantaGlobal 載入
var _pending: Array = []          # {seq, dir, walk, crouch, jump}
var _predicted := {}              # seq -> pos
var _map_site := Vector3(0, 0, 0)
var _spike_state := ""
var _connected_flag := false
var _no_server_time := 0.0
var _was_reloading := false
## 手感三件套：後座/準度模型（res://assets/recoil/recoil.json ← tools.cli recoil）
var recoil_model := RecoilModel.new()
var _recoil_key := ""
var _fire_held := false
var _auto_next := 0.0
var _burst_left := 0
var _ult_was_ready := false
var _last_mouse := Vector2.ZERO
var _footstep_timer := 0.0
var _score_atk := 0
var _score_def := 0
var _round_num := 1
var _phase_text := ""        # 買槍 / 行動 / 結算
var _phase_timer := 0.0
var _walking := false
var _phase_seen := -1
var _phase_countdown_ms := 0
var _phase_observed_ms := 0
var _settings_overlay: Control = null
var _settings_open := false
var _last_bgm_phase := -1
var _prev_mags := {}
var _death_overlay: DeathOverlay = null
var _match_results: MatchResults = null
var _flash_overlay: FlashOverlay = null
var _was_dead := false


func _ready() -> void:
	# --- 節點建立 ---
	world_render = RenderWorld.new()
	add_child(world_render)
	cam = Camera3D.new()
	cam.fov = 90.0
	add_child(cam)
	cam.make_current()
	# 第一人稱武器視角模型（程序化組裝 + 動畫）
	viewmodel = WeaponViewmodelV2.new()
	viewmodel.name = "Viewmodel"
	cam.add_child(viewmodel)
	viewmodel.position = Vector3(0.24, -0.22, -0.45)
	vfx_mgr = VFXManager.new()
	add_child(vfx_mgr)
	# 皮膚分層特效（資料驅動）+ 螢幕後鏡頭手感
	fx2 = FxManager.new()
	fx2.name = "FxLayer"
	add_child(fx2)
	screen_fx = ScreenFx.new()
	screen_fx.name = "ScreenFx"
	add_child(screen_fx)
	audio_mgr = AudioManager.new()
	add_child(audio_mgr)
	var hud_layer := CanvasLayer.new()
	hud_layer.name = "HUDLayer"
	add_child(hud_layer)
	hud = HUD.new()
	hud.name = "HUD"
	hud.add_to_group("vanta_hud")
	hud.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud_layer.add_child(hud)
	# 買槍商店
	var buy_menu_scene = load("res://buy_menu.tscn")
	if buy_menu_scene:
		var bm = buy_menu_scene.instantiate()
		hud_layer.add_child(bm)
	else:
		var bm = Control.new()
		bm.name = "BuyMenu"
		hud_layer.add_child(bm)
	net = NetClient.new()
	add_child(net)

	# --- 載入工具鏈素材索引 ---
	asset_index = _load_json("res://assets/asset_index.json")
	# 地圖（優先使用 map_default.json — 與伺服器權威地圖一致）
	var maps: Array = asset_index.get("maps", [])
	var map_path := ""
	for mp in maps:
		if String(mp).contains("default"):
			map_path = mp
			break
	if map_path == "" and maps.size() > 0:
		map_path = maps[0]
	if map_path != "":
		_map_data = _load_json(map_path)
		world_render.build_map(_map_data)
		local.set_walls(_map_data.get("walls", []))
		var sites: Array = _map_data.get("sites", [])
		if sites.size() > 0:
			_map_site = Vector3(sites[0]["center"]["x"], 0.5, sites[0]["center"]["z"])
	# 武器/音效/特效
	var wreg := WeaponRegistry.new()
	wreg.setup(asset_index)
	var bindings: Dictionary = _load_json("res://assets/fx/event_bindings.json")
	audio_mgr.setup(asset_index, bindings)
	vfx_mgr.setup(asset_index)
	_setup_skins()
	world_render.spawn_players()
	# BGM：預設戰鬥曲（工具鏈產生）
	audio_mgr.set_bgm("bgm_combat")
	# 角色畫廊（TAB 切換）
	hud.map_data = _map_data     # 小地圖資料
	gallery = AgentGallery.new()
	gallery.set_anchors_preset(Control.PRESET_FULL_RECT)
	gallery.setup(asset_index)
	hud_layer.add_child(gallery)

	# 死亡旁觀畫面
	var death_scene = load("res://death_overlay.tscn")
	if death_scene:
		_death_overlay = death_scene.instantiate()
	else:
		_death_overlay = DeathOverlay.new()
	_death_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud_layer.add_child(_death_overlay)
	# 賽後結算頁面
	var results_scene = load("res://match_results.tscn")
	if results_scene:
		_match_results = results_scene.instantiate()
	else:
		_match_results = MatchResults.new()
	_match_results.set_anchors_preset(Control.PRESET_FULL_RECT)
	hud_layer.add_child(_match_results)
	_match_results.continue_pressed.connect(_on_match_continue)
	# 閃光致盲遮罩
	var flash_scene = load("res://flash_overlay.tscn")
	if flash_scene:
		_flash_overlay = flash_scene.instantiate()
	else:
		_flash_overlay = FlashOverlay.new()
	add_child(_flash_overlay)  # CanvasLayer — 加到 root，不放在 hud_layer

	# --- 燈光（場景照明）---
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, 30, 0)
	sun.light_energy = 1.2
	sun.light_color = Color(1.0, 0.95, 0.9)
	sun.shadow_enabled = true
	add_child(sun)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.45, 0.55, 0.65)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.7, 0.72, 0.75)
	e.ambient_light_energy = 0.8
	env.environment = e
	add_child(env)

	# --- 網路（優先 VantaGlobal，fallback ProjectSettings）---
	var net_mode: String = "udp"
	var ws_url: String = "ws://127.0.0.1:8787/ws?match=demo&ai=1"
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		net_mode = g.net_mode
		ws_url = g.ws_url
	else:
		net_mode = ProjectSettings.get_setting("vanta/net_mode", "udp")
		ws_url = ProjectSettings.get_setting(
			"vanta/ws_url", ws_url)
	net.mode = net_mode
	net.ws_url = ws_url
	net.start()
	# 載入設定
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		_sens = g.sensitivity * 0.01  # 設定值轉換
		cam.fov = g.fov
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	# 出生點（工具鏈地圖的攻方第一重生點）
	var spawns: Array = _map_data.get("spawns_attackers", []) if _map_data.size() > 0 else []
	if spawns.size() > 0:
		local.pos = Vector3(spawns[0]["x"], spawns[0]["y"], spawns[0]["z"])
	# 初始視角模型（副武器）
	_apply_skin()   # 初始視角模型（含皮膚材質/貼圖/發光件）
	# 換彈里程碑音效（與伺服器進度精確對齊）
	viewmodel.reload_mag_drop.connect(func(): audio_mgr.play("mag_drop", 1.0, -4.0))
	viewmodel.reload_rack.connect(func(): audio_mgr.play("slide_rack", 1.0, -6.0))


## 載入槍皮目錄、玩家收藏，並把特效/HUD/螢幕特效接起來
func _setup_skins() -> void:
	skin_reg = SkinRegistry.shared()
	if not skin_reg.ready:
		push_warning("[main] 槍皮目錄缺失，使用標準外觀（執行 python3 -m tools.cli all 產生）")
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		if g.has_method("get_skin_progression"):
			skin_prog = g.call("get_skin_progression")
	if skin_prog == null:
		skin_prog = SkinProgression.new()
		skin_prog.name = "SkinProgression"
		add_child(skin_prog)
	fx2.setup(skin_reg, cam, screen_fx, audio_mgr, hud)
	fx2.quality = 2 if _gfx_quality_high() else 1
	fx2.muzzle_light = true
	screen_fx.camera = cam
	screen_fx.base_fov = cam.fov
	screen_fx.configure(1.0, 1 if not _gfx_quality_high() else 2)
	if skin_prog != null and skin_prog.has_signal("skin_equipped"):
		skin_prog.skin_equipped.connect(func(_w, _i): _apply_skin())
		if skin_prog.has_signal("skin_upgraded"):
			skin_prog.skin_upgraded.connect(func(_i, _l): _apply_skin())


func _gfx_quality_high() -> bool:
	return bool(ProjectSettings.get_setting("vanta/graphics/high_fx", true))


## 目前武器的 key（快照優先，退回槽位推定）
func _weapon_key() -> String:
	var w: Dictionary = net.players.get(net.slot, {}).get("weapon", {})
	var k := String(w.get("key", ""))
	if k != "":
		return k
	var slot: int = int(net.players.get(net.slot, {}).get("weapon_slot", 1))
	match slot:
		0: return "phantom"
		2: return "knife"
		_: return "classic"


## 依目前裝備的皮膚重建視角模型 + 特效色
func _apply_skin() -> void:
	if viewmodel == null:
		return
	var slot: int = int(net.players.get(net.slot, {}).get("weapon_slot", 1))
	var wid := _slot_to_weapon_id(slot)
	var key := _weapon_key()
	var res: Dictionary = {}
	if skin_prog != null and skin_reg != null and skin_reg.ready:
		res = skin_prog.resolve_current(key, wid)
	if res.is_empty() and skin_reg != null and skin_reg.ready:
		res = skin_reg.resolve("", {"weapon": key})
	_skin_res = res
	if fx2 != null:
		fx2.set_skin_resolution(res)
	viewmodel.fx_mgr = fx2
	viewmodel.build_weapon(slot, _palette(), wid, res)
	viewmodel.set_skin_resolution(res)


## 射擊命中點（Physical 層 → 彈孔/命中特效放在正確的表面上）
func _shoot_impact(dir: Vector3) -> Dictionary:
	var from: Vector3 = cam.global_position + dir * 0.55
	var to: Vector3 = cam.global_position + dir * 130.0
	var out := {"point": to, "normal": -dir, "dist": 130.0}
	var space := get_world_3d().direct_space_state
	if space == null:
		return out
	var q := PhysicsRayQueryParameters3D.create(from, to)
	q.collide_with_areas = false
	q.collide_with_bodies = true
	var hit: Dictionary = space.intersect_ray(q)
	if not hit.is_empty():
		out["point"] = hit.position
		out["normal"] = hit.normal
		out["dist"] = cam.global_position.distance_to(hit.position)
		if hit.has("collider"):
			out["collider"] = hit.collider
	return out


func _skin_fx_color(key: String, fallback: String) -> Color:
	var fx: Dictionary = _skin_res.get("fx", {})
	return SkinRegistry.hex_color(fx.get(key, fallback), SkinRegistry.hex_color(fallback))


func _process(delta: float) -> void:
	net.tick()
	_consume_events()
	_acc += delta
	while _acc >= DT:
		_acc -= DT
		var inp := _read_input()
		inp["ads"] = viewmodel._ads > 0.3
		local.ads_speed_mult = 0.76 if inp["ads"] else 1.0
		var seq: int = net.out_seq
		local.step(inp["dir"], inp["walk"], inp["crouch"], inp["jump"], DT)
		_predicted[seq] = local.pos
		_walking = inp["walk"]
		_pending.append({"seq": seq, "dir": inp["dir"], "walk": inp["walk"],
			"crouch": inp["crouch"], "jump": inp["jump"]})
		net.send_input(inp["dir"], inp["walk"], inp["crouch"], inp["jump"], inp["ads"])
	# 手感：連發泵 + 後座恢復（槍身回正）+ 準星即時跟隨擴散圓
	_pump_autofire()
	recoil_model.update(_now(), delta)
	_refresh_spread()
	# 腳步聲
	var speed := local.vel.length()
	if local.on_ground and speed > 0.5:
		_footstep_timer -= delta
		if _footstep_timer <= 0.0:
			var interval := 0.35 if _walking else 0.28
			audio_mgr.play("footstep", 0.9 + randf() * 0.2, -12.0)
			_footstep_timer = interval
	else:
		_footstep_timer = 0.0
	# 處理購買指令
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		if g.pending_buy_item_id >= 0:
			net.send_action(NetClient.ACTION_BUY, g.pending_buy_item_id, 0, 0, net.own_last_seq)
			g.pending_buy_item_id = -1
	# 快照到達後執行伺服器和解
	_reconcile()
	_update_buy_zone()
	_update_bgm_by_phase()
	_update_remote_shots()
	_update_viewmodel(delta)
	_update_hud(delta)
	_update_camera(delta)
	_update_death_overlay(delta)
	_update_flash_overlay(delta)
	if net.players.get(str(net.slot), {}).get("alive", true):
		var vel: Vector3 = net.players.get(str(net.slot), {}).get("vel", Vector3.ZERO)
		if vel.length() > 0.1:
			var to_cam := -cam.global_transform.basis.z
			var to_move := vel.normalized()
			var angle := atan2(to_move.x, to_move.z) - atan2(to_cam.x, to_cam.z)
			hud.show_damage_direction(angle)
	world_render.update_players(net, net.slot, local.pos, delta)


func _update_remote_shots() -> void:
	# 遠處玩家開槍音：快照 mag 減少 → 距離衰減 + 聲像定位（特戰級聽位）
	for s in net.players:
		if int(s) == net.slot:
			continue
		var p: Dictionary = net.players[s]
		var mag := int(p.get("mag", 0))
		var prev := _prev_mags.get(s, mag)
		_prev_mags[s] = mag
		if mag >= prev:
			continue
		if not world_render._player_nodes.has(s):
			continue
		var rig = world_render._player_nodes[s]
		if rig == null or not rig.visible:
			continue
		var to_e: Vector3 = rig.global_position - cam.global_position
		var dist := to_e.length()
		if dist > 60.0:
			continue
		var right: Vector3 = cam.global_transform.basis.x
		var pan := clampf(right.dot(to_e.normalized()), -1.0, 1.0)
		var wslot := int(p.get("weapon_slot", 0))
		var key := "vandal"
		if wslot == 1:
			key = "classic"
		elif wslot == 2:
			key = "knife"
		audio_mgr.play_synth(key, randf_range(0.92, 1.05),
			clampf(-dist * 1.1, -32.0, -5.0) - 8.0, pan)


func _update_bgm_by_phase() -> void:
	# 階段驅動 BGM：行動期 → 戰鬥曲（安放緊張曲/勝敗曲由事件層接管）
	var phase := net.match_phase
	if phase != _last_bgm_phase:
		_last_bgm_phase = phase
		if phase == NetClient.PHASE_ACTION:
			audio_mgr.set_bgm("bgm_combat")
		elif phase == NetClient.PHASE_BUY:
			audio_mgr.set_bgm("bgm_menu")


func _read_input() -> Dictionary:
	var f := 0.0
	var s := 0.0
	if Input.is_key_pressed(KEY_W):
		f += 1.0
	if Input.is_key_pressed(KEY_S):
		f -= 1.0
	if Input.is_key_pressed(KEY_D):
		s += 1.0
	if Input.is_key_pressed(KEY_A):
		s -= 1.0
	var walk := Input.is_key_pressed(KEY_SHIFT)
	var crouch := Input.is_key_pressed(KEY_CTRL)
	var jump := Input.is_key_pressed(KEY_SPACE) and not _jump_held
	_jump_held = Input.is_key_pressed(KEY_SPACE)
	# 鏡頭相對移動：把 (strafe, forward) 依 yaw 旋轉成世界方向。
	# 鏡頭前向 F=(sin yaw, cos yaw)，右向 R=F×up=(-cos yaw, sin yaw)
	# world = R*s + F*f（伺服器 MoveInput 為世界軸慣例：strafe→+x、forward→+z）
	var sy := sin(_yaw)
	var cy := cos(_yaw)
	return {
		"dir": Vector2(-cy * s + sy * f, sy * s + cy * f),
		"walk": walk, "crouch": crouch, "jump": jump,
	}


## 技能索引 → vfx2 藍圖 id（tools/vfx/blueprints.py 的 ability_* 家族）
func _ability_blueprint(index: int) -> String:
	match index:
		0:
			return "ability_smoke"
		1:
			return "ability_flash"
		2:
			return "ability_frag"
		_:
			return "ability_dash"


## 終點球：把权威封包裡的 {points, cost, ready} 套到 HUD，並在 ready 的上升沿給回饋
func _sync_ult(state: Dictionary) -> void:
	var pts := int(state.get("points", 0))
	var cost := int(state.get("cost", 0))
	var ready := bool(state.get("ready", false))
	hud.set_ult(pts, cost, ready, bool(state.get("blocked", false)))
	if ready and not _ult_was_ready:
		_ult_was_ready = true
		audio_mgr.play_synth("ult_ready_chime", 1.0, -4.0)
		hud.announce("終點球就緒 — 按 X", Color(1.0, 0.8, 0.25))
		# 藍圖自帶 audio（tools/vfx/blueprints.py）→ 有 fx2 時不重複播音效
		if fx2 != null:
			fx2.play("ult_ready", {"impact": cam.global_position + Vector3(0, -0.45, 0),
					"scale": 1.0})
		else:
			audio_mgr.play_synth("ult_ready_chime", 1.0, -4.0)
	elif not ready and _ult_was_ready:
		_ult_was_ready = false


## 一般技能：本地只做「次數/冷卻」顯示與攔截提示，能不能放仍由伺服器決定
func _cast_ability(index: int, label: String) -> void:
	var left := 0
	if hud.ability_charges.size() > index:
		left = int(hud.ability_charges[index])
	if left <= 0 and hud.ability_cooldowns[index] <= 0.0:
		# 沒有使用次數且不在冷卻 → 真的放不出來（伺服器也會拒），給個清楚的提示
		audio_mgr.play_synth("ui_error", 1.0, -12.0)
		hud.announce("技能 %s 沒有可用次數" % label, Color(1.0, 0.5, 0.35))
		return
	net.send_action(NetClient.ACTION_ABILITY, index,
			int(_yaw * 100), int(_pitch * 100), net.own_last_seq)
	var fwd2: Vector3 = -cam.global_transform.basis.z
	if fx2 != null:
		fx2.play(_ability_blueprint(index), {"impact": cam.global_position + fwd2 * 2.0,
				"dir": fwd2, "scale": 1.0})
	else:
		audio_mgr.play_synth("ability_cast", 1.0 + 0.06 * float(index), -8.0)
	if left > 1:
		hud.announce("技能 %s 發動（剩 %d）" % [label, left - 1], Color(0.3, 0.9, 1.0))
	else:
		hud.announce("技能 %s 發動！" % label, Color(0.3, 0.9, 1.0))


## 施放終點球（X）：本地只做「還沒充能就別發包」的閘門，判定仍歸伺服器
func _try_cast_ult() -> void:
	if not hud.ult_ready:
		audio_mgr.play_synth("ui_error", 1.0, -10.0)
		hud.announce("終點球尚未就緒  %d / %d" % [hud.ult_points, maxi(1, hud.ult_cost)],
			Color(1.0, 0.45, 0.35))
		return
	net.send_action(NetClient.ACTION_ABILITY, 3,
			int(_yaw * 100), int(_pitch * 100), net.own_last_seq)
	screen_fx.add_trauma(0.22)
	var fwd := -cam.global_transform.basis.z
	if fx2 != null:
		fx2.play("ult_cast", {"impact": cam.global_position + fwd * 1.2, "dir": fwd,
				"scale": 1.25})
	else:
		audio_mgr.play_synth("ult_cast", 1.0, -2.0)
	_ult_was_ready = false   # 等下一個权威包確認；避免同一幀重複觸發


func _now() -> float:
	return float(Time.get_ticks_msec()) / 1000.0


func _current_weapon_key() -> String:
	return String(net.players.get(net.slot, {}).get("weapon", {}).get("key", "classic"))


## 換槍 → 載入該槍的图案（金鑰＝伺服器武器 key）
func _ensure_recoil_model(key: String) -> void:
	if key == _recoil_key:
		return
	_recoil_key = key
	var ok := recoil_model.setup(key)
	if viewmodel != null:
		# 有資料 → 視角由模型獨佔（避免兩套恢復曲線互相拉扯）
		viewmodel.recoil_model_driven = bool(ok)


## 開火：網路封包 + 視角模型 + 音效 + 命中特效（auto＝連發泵補的發）
func _try_fire(_from_auto: bool) -> void:
	if net.match_phase != 1:
		return
	var me: Dictionary = net.players.get(net.slot, {})
	var is_knife: bool = int(me.get("weapon_slot", 1)) == 2
	var wk: String = String(me.get("weapon", {}).get("key", "classic"))
	_ensure_recoil_model(wk)
	# 彈匣見底就别再發包（伺服器會自己觸發換彈）
	if recoil_model.has_data and int(me.get("weapon", {}).get("mag", -1)) <= 0:
		_fire_held = false
		_burst_left = 0
		return
	net.send_shot(_yaw, _pitch)
	var aim_dir: Vector3 = -cam.global_transform.basis.z
	if is_knife:
		viewmodel.play_knife()
		var sfx_k := String(_skin_res.get("fx", {}).get("sound_key", ""))
		audio_mgr.play_synth("knife_swing" if sfx_k == "" else sfx_k,
			float(_skin_res.get("fx", {}).get("sound_pitch", 1.0)), -8.0)
	elif not recoil_model.has_data:
		# 缺 bundle（尚未跑工具鏈）→ 退回舊的近似行為，別讓準星變成死的
		viewmodel.play_fire(randf_range(0.5, 1.0))
		hud.spread_angle = minf(hud.spread_angle + 1.5, 5.0)
	else:
		# 這一發的真實偏移 → 槍身 kick（不再用 randf 猜）
		var dv := recoil_model.fire(_now())
		viewmodel.play_fire(dv.x)
		viewmodel.set_recoil(recoil_model.pitch, recoil_model.yaw)
		_refresh_spread()
		# 合成槍聲：武器音色 + 皮膚招牌音色（工具鏈 SFX_REGISTRY）
		var sfx: Dictionary = _skin_res.get("fx", {})
		var pitch := float(sfx.get("sound_pitch", 1.0))
		var gain := float(sfx.get("sound_gain_db", 0.0))
		audio_mgr.play_synth(wk, pitch, -10.0 + gain * 0.5)
		var skey := String(sfx.get("sound_key", ""))
		if skey != "":
			audio_mgr.play_synth(skey, pitch, gain - 4.0)
	# 命中點（射線）→ 槍口/曳光/彈孔/命中特效全部放對位置
	var impact := _shoot_impact(aim_dir)
	if fx2 != null and not _skin_res.is_empty():
		fx2.fire(viewmodel.muzzle_transform(), aim_dir, impact, _skin_res, is_knife)
	else:
		vfx_mgr.spawn("muzzle_flash", cam.global_position + aim_dir * 0.6)
		vfx_mgr.spawn_tracer(cam.global_position + aim_dir * 0.8, aim_dir, 30.0)
	if not is_knife and float(impact.get("dist", 99.0)) < 55.0 and fx2 != null:
		fx2.play(skin_reg.impact_blueprint(_skin_res) if skin_reg != null else "impact_default", {
			"impact": impact.get("point", Vector3.ZERO),
			"normal": impact.get("normal", Vector3.UP),
			"dir": aim_dir, "res": _skin_res,
			"scale": float(_skin_res.get("fx", {}).get("muzzle_scale", 1.0)),
		})
	if screen_fx != null:
		screen_fx.add_trauma(0.035 if not is_knife else 0.02)


## 連發泵：automatic → 按住依射速補發；burst → 一次排程打完那組
## 射速取自 bundle，伺服器的 next_fire_time 同速限流，因此不會超發
func _pump_autofire() -> void:
	if net.match_phase != 1:
		_fire_held = false
		_burst_left = 0
		return
	if _burst_left <= 0 and not _fire_held:
		return
	if _now() < _auto_next:
		return
	var me: Dictionary = net.players.get(net.slot, {})
	if int(me.get("weapon_slot", 1)) == 2:
		_burst_left = 0
		return
	_ensure_recoil_model(String(me.get("weapon", {}).get("key", "classic")))
	if _burst_left > 0:
		_burst_left -= 1
	elif not recoil_model.automatic:
		return   # 半自動：放開再按才算下一發
	else:
		pass
	_try_fire(true)
	_auto_next = _now() + recoil_model.fire_interval


## 準星＝真的擴散圓（度 → HUD 直接照這個半徑畫）
func _refresh_spread() -> void:
	if hud == null or recoil_model == null:
		return
	if hud.recoil_model != recoil_model:
		hud.recoil_model = recoil_model
	var ratio := 0.0
	if local != null and local.max_speed() > 0.0:
		ratio = clampf(local.vel.length() / local.max_speed(), 0.0, 1.0)
	var ads: bool = viewmodel != null and viewmodel._ads > 0.3
	if not recoil_model.has_data:
		hud.release_spread()
		return
	var air: bool = not local.on_ground
	var deg: float = recoil_model.spread_deg(ratio, local.walking, local.crouching,
			air, local.time_since_land, ads)
	hud.set_spread_deg(deg)
	# 移動狀態回饋（準度的來源）：剛落地 > 空中 > 蹲 > 靜步 > 站/跑
	var st := 0
	if local.time_since_land < recoil_model._land_time:
		st = 4
	elif air:
		st = 3
	elif local.crouching:
		st = 2
	elif local.walking and ratio > 0.01:
		st = 1
	hud.set_spread_state(st)


func _unhandled_input(event: InputEvent) -> void:
	if _settings_open:
		return
	if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
		_yaw += -event.relative.x * _sens
		_pitch -= event.relative.y * _sens
		_pitch = clampf(_pitch, -1.35, 1.35)
		_last_mouse = event.relative
	elif event is InputEventMouseButton and event.pressed:
		match event.button_index:
			MOUSE_BUTTON_LEFT:
				_fire_held = true
				_ensure_recoil_model(_current_weapon_key())
				_burst_left = 0
				_try_fire(false)
				# 連發武器（automatic）靠 _pump_autofire 續發；連發數（burst）在此排程
				if recoil_model.has_data and not recoil_model.automatic \
						and recoil_model.burst_count > 1:
					_burst_left = recoil_model.burst_count - 1
				_auto_next = _now() + recoil_model.fire_interval
			MOUSE_BUTTON_RIGHT:
				viewmodel.set_ads(true)
	elif event is InputEventMouseButton and not event.pressed \
			and event.button_index == MOUSE_BUTTON_RIGHT:
		viewmodel.set_ads(false)
	elif event is InputEventMouseButton and not event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		_fire_held = false
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1:
				net.send_action(NetClient.ACTION_SWITCH, 0, 0, 0, net.own_last_seq)
			KEY_2:
				net.send_action(NetClient.ACTION_SWITCH, 1, 0, 0, net.own_last_seq)
			KEY_3:
				net.send_action(NetClient.ACTION_SWITCH, 2, 0, 0, net.own_last_seq)
			KEY_Q:
				_cast_ability(1, "Q")
			KEY_E:
				_cast_ability(2, "E")
			KEY_C:
				_cast_ability(0, "C")
			KEY_X:
				_try_cast_ult()   # 終點球：需充能滿（權威在伺服器，這裡只擋掉明顯無效的按鍵）
			KEY_R:
				net.send_action(NetClient.ACTION_RELOAD, 0, 0, 0, net.own_last_seq)
			KEY_Y:
				viewmodel.play_inspect()        # 檢視武器（特戰按鍵：Y）
			KEY_F:
				pass                             # F = 互動/撿武器（特戰按鍵；本專案預留）
			KEY_B:
				# B = 開啟買槍商店
				var bm = get_node_or_null("HUDLayer/BuyMenu")
				if not bm:
					bm = get_tree().current_scene.get_node_or_null("BuyMenu")
				if bm and bm.has_method("is_open"):
					if bm.is_open():
						bm.close_menu()
						Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
					else:
						var credits: int = int(net.match_credits[net.slot]) if net.match_credits.size() > net.slot and net.slot >= 0 else 8000
						bm.open_menu(credits)
						Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_F1:
				_toggle_observer()
			KEY_F2:
				_toggle_practice_ui()
			KEY_F3:
				_toggle_mission_ui()
			KEY_F4:
				_open_replay_viewer()
	elif event is InputEventKey and event.pressed and event.keycode == KEY_TAB:
		gallery.toggle()
		if gallery.visible_now:
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
		else:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	elif event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		_toggle_settings()


func _toggle_observer() -> void:
	if _observer_node == null:
		if has_node("/root/Main/ObserverMode"):
			_observer_node = get_node("/root/Main/ObserverMode")
		else:
			_observer_node = ObserverMode.new()
			_observer_node.name = "ObserverMode"
			add_child(_observer_node)
			_observer_node.setup(cam, net)
	if _observer_node and _observer_node.has_method("toggle"):
		_observer_node.toggle()


func _toggle_practice_ui() -> void:
	if _practice_ui_node == null:
		_practice_ui_node = get_node_or_null("/root/Main/PracticeUI")
		if _practice_ui_node == null:
			_practice_ui_node = preload("res://practice_range.tscn").instantiate() if ResourceLoader.exists("res://practice_range.tscn") else null
			if _practice_ui_node:
				add_child(_practice_ui_node)
	if _practice_ui_node:
		_practice_ui_node.visible = not _practice_ui_node.visible


func _toggle_mission_ui() -> void:
	var mission = get_node_or_null("/root/Main/MissionUI")
	if mission == null:
		mission = preload("res://mission_ui.tscn").instantiate() if ResourceLoader.exists("res://mission_ui.tscn") else null
		if mission:
			add_child(mission)
	if mission:
		mission.visible = not mission.visible


func _open_replay_viewer() -> void:
	var dir := DirAccess.open("user://replays")
	if dir == null:
		DirAccess.make_dir_absolute("user://replays")
		dir = DirAccess.open("user://replays")
	var latest := ""
	var latest_time := 0
	if dir:
		dir.list_dir_begin()
		var fname := dir.get_next()
		while fname != "":
			if fname.ends_with(".vrep"):
				var ftime = dir.get_modified_time(fname)
				if ftime > latest_time:
					latest_time = ftime
					latest = fname
			fname = dir.get_next()
		dir.list_dir_end()
	if latest != "":
		var replay_scene = preload("res://replay_viewer.tscn") if ResourceLoader.exists("res://replay_viewer.tscn") else null
		if replay_scene:
			var rv = replay_scene.instantiate()
			add_child(rv)
			if rv.has_method("load_replay"):
				rv.load_replay("user://replays/" + latest)


func _toggle_settings() -> void:
	# 遊戲內設定覆蓋層（ESC 開關）：靈敏度/準心/音量/畫質
	if _settings_overlay == null:
		_settings_overlay = Control.new()
		_settings_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
		_settings_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
		var scene := load("res://settings.tscn")
		if scene:
			var inst: Node = scene.instantiate()
			_settings_overlay.add_child(inst)
			# 載入目前設定（settings_menu 預設值 vs VantaGlobal）
			if has_node("/root/VantaGlobal") and inst.has_method("_load_from_global") == false:
				var g := get_node("/root/VantaGlobal")
				if "sensitivity" in inst:
					inst.sensitivity = g.sensitivity
				if "ads_sensitivity" in inst:
					inst.ads_sensitivity = g.ads_sensitivity
		var resume := Button.new()
		resume.text = "返回遊戲（ESC）"
		resume.position = Vector2(20, 16)
		resume.pressed.connect(_toggle_settings)
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.12, 0.14, 0.18)
		sb.corner_radius_top_left = 4
		sb.corner_radius_top_right = 4
		sb.corner_radius_bottom_left = 4
		sb.corner_radius_bottom_right = 4
		resume.add_theme_stylebox_override("normal", sb)
		_settings_overlay.add_child(resume)
		add_child(_settings_overlay)
	_settings_open = not _settings_open
	_settings_overlay.visible = _settings_open
	if _settings_open:
		Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	else:
		Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
		# 立即套用新的準心／手感設定
		if hud != null and hud.has_method("reload_crosshair_config"):
			hud.call("reload_crosshair_config")
		# 立即套用新的滑鼠靈敏度
		if has_node("/root/VantaGlobal"):
			_sens = float(get_node("/root/VantaGlobal").sensitivity) * 0.01


func _reconcile() -> void:
	var me: Dictionary = net.players.get(net.slot, {})
	if me.is_empty():
		return
	var last_seq: int = me.get("last_seq", -1)
	var server_pos: Vector3 = me["pos"]
	if last_seq >= 0 and _predicted.has(last_seq):
		var pp: Vector3 = _predicted[last_seq]
		if pp.distance_to(server_pos) > 0.25:
			# 回退到伺服器狀態，重放未確認輸入
			local.pos = server_pos
			local.vel = me["vel"]
			local.on_ground = me["on_ground"]
			for p in _pending:
				if int(p["seq"]) > last_seq:
					local.step(p["dir"], p["walk"], p["crouch"], p["jump"], DT)
	# 清除已確認
	_pending = _pending.filter(func(p): return int(p["seq"]) > last_seq)
	for k in _predicted.keys():
		if k <= last_seq:
			_predicted.erase(k)


func _consume_events() -> void:
	for ev in net.events:
		match int(ev["event"]):
			NetClient.EV_KILL:
				var killer := int(ev["p0"])
				var victim := int(ev["p1"])
				hud.push_feed("P%02d 擊殺 P%02d" % [killer, victim])
				var vp: Vector3 = net.players.get(victim, {}).get("pos", Vector3.ZERO)
				if vp != Vector3.ZERO:
					vfx_mgr.spawn("kill_confirm", vp + Vector3(0, 1, 0))
				if killer == net.slot and victim != net.slot:
					# 我的擊殺：橫幅 + 紅 X + 連殺語音 + hitmarker + 皮膚擊殺特效
					var wk: String = net.players.get(net.slot, {}).get("weapon", {}).get("key", "")
					hud.killflash(false)
					if fx2 == null or _skin_res.is_empty():
						hud.show_kill_banner("P%02d" % victim, false, wk)
					audio_mgr.play_hitmarker()
					audio_mgr.play_kill()
					if fx2 != null and not _skin_res.is_empty():
						fx2.play(skin_reg.kill_blueprint(_skin_res), {
							"victim": vp + Vector3(0, 1.0, 0), "impact": vp + Vector3(0, 1.0, 0),
							"victim_name": "P%02d" % victim, "res": _skin_res, "hud": hud,
							"scale": 1.0 + 0.06 * int(_skin_res.get("level", 1)),
						})
					if screen_fx != null:
						screen_fx.on_kill(_skin_fx_color("kill_color", "#ffdd66"))
				elif victim == net.slot:
					audio_mgr.play("damage_taken", 0.9, -2.0)
					# 死亡旁觀畫面
					var killer_name := "P%02d" % killer
					var killer_wk: String = ""
					var killer_pos: Vector3 = net.players.get(killer, {}).get("pos", Vector3.ZERO)
					var my_pos: Vector3 = net.players.get(net.slot, {}).get("pos", Vector3.ZERO)
					var dist := killer_pos.distance_to(my_pos)
					if _death_overlay:
						_death_overlay.set_own_info(net.slot, 0 if net.slot < 5 else 1)
						_death_overlay.show_death(killer_name, killer_wk, false, dist)
			NetClient.EV_SPIKE_PLANTED:
				hud.announce("Spike 已安放！", Color(1.0, 0.3, 0.3))
				audio_mgr.play_event(NetClient.EV_SPIKE_PLANTED)
				audio_mgr.set_bgm("bgm_tension")
			NetClient.EV_SPIKE_DEFUSED:
				hud.announce("Spike 已拆除", Color(0.3, 1.0, 0.6))
				audio_mgr.play_event(NetClient.EV_SPIKE_DEFUSED)
			NetClient.EV_SPIKE_DETONATED:
				hud.announce("Spike 爆炸！", Color(1.0, 0.5, 0.1))
				vfx_mgr.spawn("explosion_debris", _map_site)
				audio_mgr.play_event(NetClient.EV_SPIKE_DETONATED)
			NetClient.EV_ROUND_WIN:
				hud.announce("回合勝利", Color(0.3, 1.0, 0.5))
				audio_mgr.play_round_result(true, net.slot >= 0 and net.slot < 5)
				audio_mgr.set_bgm("bgm_victory")
			NetClient.EV_ROUND_LOSS:
				hud.announce("回合敗北", Color(1.0, 0.4, 0.4))
				audio_mgr.play_round_result(false, net.slot >= 0 and net.slot < 5)
				audio_mgr.set_bgm("bgm_defeat")
			NetClient.EV_MATCH_END:
				hud.announce("比賽結束", Color(1.0, 0.85, 0.3))
				audio_mgr.play_event(NetClient.EV_MATCH_END)
				# 賽後結算畫面
				var won := net.match_score_a > net.match_score_b if net.slot < 5 else net.match_score_b > net.match_score_a
				if _match_results and _match_results.visible == false:
					var round_records: Array = []
					if net.has_method("get_round_records"):
						round_records = net.get_round_records()
					_match_results.show_results(won, net.match_score_a, net.match_score_b,
						round_records, net.players, net.slot, 0 if net.slot < 5 else 1)
			NetClient.EV_ASSIST:
				var assister := int(ev["p0"]); var victim2 := int(ev["p1"])
				if assister == net.slot:
					hud.announce("助攻 +1", Color(0.5, 0.8, 1.0))
					hud.push_feed("助攻 P%02d" % victim2)
					audio_mgr.play_hitmarker()
			NetClient.EV_STREAK:
				var streak := int(ev["p0"]); var killer2 := int(ev["p1"])
				var names := {2:"DOUBLE KILL",3:"TRIPLE KILL",4:"QUAD KILL",5:"ACE"}
				var nm: String = names.get(streak, "%d KILL" % streak)
				hud.announce(nm, Color(1.0, 0.75, 0.1) if streak >=4 else Color(1.0, 0.85, 0.3))
				if killer2 == net.slot: audio_mgr.play_kill()
			NetClient.EV_CLUTCH:
				var wh := int(ev["p0"]); var vs := int(ev["p1"])
				hud.announce("殘局 1v%d" % vs, Color(1.0, 0.4, 0.2))
				hud.push_feed("殘局 P%02d 1v%d" % [wh, vs])
			NetClient.EV_ORB:
				var kind_i := int(ev["p0"]); var who := int(ev["p1"])
				var kind_names := ["武器升級","全隊治療","刺激","偏執","金槍"]
				var kn: String = kind_names[kind_i] if kind_i < kind_names.size() else str(kind_i)
				if who == net.slot: hud.announce("能量球：%s" % kn, Color(0.4, 0.9, 0.6))
	net.events.clear()


func _update_viewmodel(delta: float) -> void:
	# 由快照差異驅動動畫：換槍 → switch；換彈 → reload；彈匣減少 → 開火
	var me: Dictionary = net.players.get(net.slot, {})
	if me.is_empty():
		return
	var slot: int = me.get("weapon_slot", viewmodel.weapon_slot)
	if slot != viewmodel.weapon_slot:
		viewmodel.play_switch_out()
		_apply_skin()
		viewmodel.play_switch_in()
		audio_mgr.play("vandalreload", 0.8, -6.0)
	# 軍械庫換裝／升級 → 即時生效
	if has_node("/root/VantaGlobal"):
		var g2 := get_node("/root/VantaGlobal")
		var rev := int(g2.get("skin_revision"))
		if rev != _skin_rev:
			_skin_rev = rev
			_apply_skin()
	var reloading: bool = me.get("reloading", false)
	if reloading and not _was_reloading:
		viewmodel.begin_reload_from_server()
		audio_mgr.play("reload")
	elif _was_reloading and not reloading:
		# 與伺服器 weapon_state.update() 同步：換彈完成 → 图案從第 1 發重來
		recoil_model.reset_pattern()
		_refresh_spread()
	var wk := String(me.get("weapon", {}).get("key", ""))
	if wk != "" and wk != _recoil_key:
		# 換槍 → 換图案，並把準星/視角歸零（不帶著上一把的後座開槍）
		_ensure_recoil_model(wk)
		recoil_model.hard_reset()
		_refresh_spread()
	_was_reloading = reloading
	# 步態 bob + 伺服器換彈進度（精確驅動動畫/音效時序）
	var speed: float = local.vel.length()
	var rfrac: float = me.get("reload_frac", -1.0)
	viewmodel.update(delta, speed, local.on_ground, _last_mouse, rfrac)
	# 最後蓋上後座偏移：順序在 viewmodel.update 之後，才不會被它的動畫覆蓋
	if recoil_model.has_data:
		viewmodel.set_recoil(recoil_model.pitch, recoil_model.yaw)


## 武器槽位 → 武器 ID 對照
## slot 0 = 主武器（Phantom 幻象）
## slot 1 = 副武器（Classic 經典）
## slot 2 = 近戰（匕首）
func _slot_to_weapon_id(slot: int) -> int:
	match slot:
		0: return 0   # Phantom
		1: return 3   # Classic
		_: return 4   # 匕首


func _palette() -> Dictionary:
	# 已裝備皮膚 → 用皮膚色板（保持 UI/預覽與遊戲內一致）
	if not _skin_res.is_empty():
		var cw: Dictionary = _skin_res.get("colorway", {})
		return {
			"primary": SkinRegistry.hex_color(cw.get("primary", "#2b2f38"), Color(0.25, 0.27, 0.32)),
			"accent": SkinRegistry.hex_color(cw.get("accent", "#ff7a35"), Color(0.85, 0.4, 0.25)),
			"skin_name": String(_skin_res.get("name", "")),
			"weapon_key": _weapon_key(),
		}
	# 從武器工坊讀取自訂配色
	if has_node("/root/VantaGlobal"):
		var g := get_node("/root/VantaGlobal")
		if g.weapon_palette.has("primary"):
			return {
				"primary": g.weapon_palette["primary"],
				"accent": g.weapon_palette["accent"]
			}
	return {
		"primary": Color(0.25, 0.27, 0.32),
		"accent": Color(0.85, 0.4, 0.25)
	}


func _update_buy_zone() -> void:
	# 買槍階段 → 限制在出生區；其餘階段解除（與伺服器一致）
	if net.match_phase == 0 and net.slot >= 0:
		var zone_key := "buy_zone_attackers" if net.slot < 5 else "buy_zone_defenders"
		var zone: Variant = _map_data.get(zone_key)
		if zone is Array and zone.size() >= 2:
			local.set_buy_zone(
				Vector3(zone[0]["x"], zone[0]["y"], zone[0]["z"]),
				Vector3(zone[1]["x"], zone[1]["y"], zone[1]["z"]))
			return
	local.clear_buy_zone()


func _update_hud(delta: float) -> void:
	_phase_timer = maxf(0.0, _phase_timer - delta)
	# ── 從 MatchState（0x06）取伺服器權威資料 ──
	var phase_names := {0: "買槍", 1: "行動", 2: "結算", 3: "比賽結束"}
	var ms_phase: String = phase_names.get(net.match_phase, "")
	# 回合倒數：階段切換時以伺服器 timer 為基準，之後本地倒數
	if net.match_phase != _phase_seen and net.match_timer_ms >= 0:
		_phase_seen = net.match_phase
		_phase_countdown_ms = net.match_timer_ms
		_phase_observed_ms = Time.get_ticks_msec()
	if _phase_countdown_ms > 0:
		var remain := int(ceilf(float(_phase_countdown_ms - (Time.get_ticks_msec() - _phase_observed_ms)) / 1000.0))
		hud.round_timer = maxi(0, remain)
	else:
		hud.round_timer = -1
	# 共通資料
	hud.players_dict = net.players
	hud.own_slot = net.slot
	# 比分/回合：優先用 match state；fallback 到本地計數（event）
	if net.match_phase >= 0:
		hud.score_attack = net.match_score_a
		hud.score_defend = net.match_score_b
		hud.round_number = net.match_round
		hud.phase_text = ms_phase
	else:
		hud.score_attack = _score_atk
		hud.score_defend = _score_def
		hud.round_number = _round_num
	# 金錢
	if net.match_credits.size() > net.slot and net.slot >= 0:
		hud.credits = int(net.match_credits[net.slot])
	# 技能冷卻／使用次數／終點球（权威值來自 0x07 ABILITY_STATE，每秒一包）
	if net.ability_cooldowns.size() > net.slot and net.slot >= 0:
		var my_cds: Array = net.ability_cooldowns[net.slot]
		for i in range(mini(4, my_cds.size())):
			var cd: float = float(my_cds[i])
			hud.ability_cooldowns[i] = cd
			# 最大冷卻從「實際見到的第一個值」推得，不再寫死 [10,10,0,0]
			if cd > 0.0 and cd > float(hud.ability_max_cds[i]):
				hud.ability_max_cds[i] = cd
		if net.ability_charges.size() > net.slot:
			hud.ability_charges = (net.ability_charges[net.slot] as Array).duplicate()
		if net.ability_ult.size() > net.slot:
			_sync_ult(net.ability_ult[net.slot])
		else:
			var me2: Dictionary = net.players.get(net.slot, {})
			if me2.has("ult"):
				_sync_ult(me2["ult"])
	# Spike 狀態
	var spike_names := {0: "", 1: "安放中...", 2: "已安放", 3: "拆除中...", 4: "爆炸!", 5: "已拆除"}
	var spike_txt: String = spike_names.get(net.match_spike_state, "")
	if net.match_spike_state == 2 and net.match_spike_fuse > 0:
		spike_txt = "已安放 (%ds)" % net.match_spike_fuse
	hud.set_spike(spike_txt)
	if net.connected and net.slot >= 0:
		hud.connected_text = "已連線"
		hud.ping_text = str(int(net.rtt_ms))
		hud.tick_text = str(net.last_server_tick)
		var me: Dictionary = net.players.get(net.slot, {})
		if not me.is_empty():
			hud.health = int(me.get("health", 100))
			hud.shield = int(me.get("shield", 0))
			hud.mag = int(me.get("mag", 0))
			hud.weapon_slot = int(me.get("weapon_slot", 1))
			match hud.weapon_slot:
				0: hud.weapon_name = "步槍"
				1: hud.weapon_name = "手槍"
				2: hud.weapon_name = "刀"
				_: hud.weapon_name = "武器"
	else:
		_no_server_time += delta
		if _no_server_time < 2.0:
			hud.connected_text = "連線中…"
		else:
			hud.connected_text = "伺服器未連線"
	# 開鏡 + 狙擊鏡狀態 + 移動減速
	hud.is_ads = viewmodel._ads > 0.3
	local.ads_speed_mult = 0.6 if viewmodel._ads > 0.5 else 1.0
	var me2: Dictionary = net.players.get(net.slot, {})
	var wk: String = me2.get("weapon", {}).get("key", "classic")
	hud.is_scoped = wk in ["marshal", "operator"]


func _update_camera(delta: float) -> void:
	var eye := CROUCH_EYE if local.crouching else EYE_HEIGHT
	var aim := Vector3(
		sin(_yaw) * cos(_pitch),
		sin(_pitch),
		cos(_yaw) * cos(_pitch)
	)
	var target := local.pos + Vector3(0, eye, 0)
	var cur: Vector3 = cam.global_position
	cam.global_position = cur.lerp(target, 1.0 - exp(-20.0 * delta))
	cam.look_at(cam.global_position + aim, Vector3.UP)
	# FOV 縮放（開鏡時 90→50）
	var ads_t: float = viewmodel._ads
	var scoped := ads_t > 0.5 and _weapon_key() in ["operator", "marshal", "outlaw"]
	var target_fov := 50.0 if ads_t > 0.5 else 90.0
	cam.fov = lerpf(cam.fov, target_fov, 1.0 - exp(-10.0 * delta))
	# 螢幕後特效：創傷式震動 / 暗角 / 速度線（由 ScreenFx 供應偏移量）
	if screen_fx != null:
		var pd: Dictionary = net.players.get(net.slot, {})
		var hp := float(pd.get("hp", pd.get("health", 100)))
		screen_fx.ads_amount = ads_t
		screen_fx.speed_amount = clampf(local.vel.length() / 6.2, 0.0, 1.0)
		screen_fx.low_health = clampf(1.0 - hp / 100.0, 0.0, 1.0) * 0.85
		screen_fx.set_scope(scoped)
		cam.global_position += screen_fx.position_offset()
		cam.rotation.z = screen_fx.roll()
		cam.fov = clampf(cam.fov + screen_fx.fov_delta(), 45.0, 120.0)


func _load_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var parsed = JSON.parse_string(f.get_as_text())
	return parsed if parsed is Dictionary else {}


func _update_death_overlay(delta: float) -> void:
	if _death_overlay == null:
		return
	# 更新旁觀畫面的外部資料
	_death_overlay.players_dict = net.players
	_death_overlay.round_timer = hud.round_timer
	_death_overlay.phase_text = hud.phase_text
	# 檢測復活（從死亡變為存活）
	var me: Dictionary = net.players.get(net.slot, {})
	if not me.is_empty():
		var alive := int(me.get("health", 0)) > 0
		if _was_dead and alive:
			_death_overlay.hide_death()
			_was_dead = false
		elif not _was_dead and not alive:
			_was_dead = true


func _on_match_continue() -> void:
	# 賽後結算 → 返回主選單
	if _match_results:
		_match_results.hide_results()
	get_tree().change_scene_to_file("res://menu.tscn")


func _update_flash_overlay(delta: float) -> void:
	# 處理閃光致盲事件隊列
	if _flash_overlay == null:
		return
	net.update_flash_blind(delta)
	for ev in net.flash_blind_events:
		var intensity: float = ev.get("intensity", 0.8)
		_flash_overlay.trigger(intensity)
	net.flash_blind_events.clear()


var _practice_range: Node = null
var _practice_ui_node = null
var _observer_node = null

var _offline_flash_cooldown := 0.0
func _passive_flash_check(delta: float) -> void:
	# 離線模式：距離最近的活著 bot < 8m 且 bot 朝向自己 → 概率觸發閃光
	# （離線模式沒有伺服器閃光事件，用近似模擬）
	_offline_flash_cooldown = maxf(0.0, _offline_flash_cooldown - delta)
	if _offline_flash_cooldown > 0.0:
		return
	var my_pos: Vector3 = net.players.get(net.slot, {}).get("pos", Vector3.ZERO)
	for i in range(5, 10):
		var bp: Dictionary = net.players.get(i, {})
		if bp.get("health", 0) <= 0:
			continue
		var dist: float = my_pos.distance_to(bp["pos"])
		if dist < 6.0 and randf() < 0.02:
			# bot 朝向自己 → 閃光命中
			net.trigger_flash_blind(0.85, 1.8)
			_offline_flash_cooldown = 4.0
			return
