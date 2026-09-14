class_name SocialUI
extends Control

## VANTA 社交 UI — 好友列表/聊天/個人資料/排位顯示
## 從主選單右上角好友圖示進入

signal close_requested()

var social = null
var current_tab := "friends"  # friends / chat / profile / rank
var chat_channel := "global"
var chat_input: LineEdit = null
var chat_log: RichTextLabel = null
var friend_list_container: VBoxContainer = null
var profile_container: VBoxContainer = null
var rank_container: VBoxContainer = null
var tab_buttons: Dictionary = {}


func _ready() -> void:
	# 取得 SocialSystem
	social = get_node_or_null("/root/VantaGlobal/SocialSystem")
	if social == null:
		social = preload("res://scripts/social_system.gd").new()
		social.name = "SocialSystem"
		get_node("/root/VantaGlobal").add_child(social)

	_build_ui()
	_switch_tab("friends")


func _build_ui() -> void:
	# 全屏半透明背景
	var bg := ColorRect.new()
	bg.color = Color(0.0, 0.0, 0.0, 0.85)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	# 主面板
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(900, 600)
	panel.position = Vector2(-450, -300)
	panel.size = Vector2(900, 600)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.08, 0.08, 0.12)
	style.border_color = Color(0.2, 0.2, 0.3)
	style.border_width_left = 2
	style.border_width_right = 2
	style.border_width_top = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	panel.add_theme_stylebox_override("panel", style)
	add_child(panel)

	var main_vbox := VBoxContainer.new()
	main_vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	main_vbox.add_theme_constant_override("separation", 0)
	panel.add_child(main_vbox)

	# ── 標題列 ──
	var title_bar := _make_hbox(40)
	var title_label := Label.new()
	title_label.text = "👥 社交"
	title_label.add_theme_font_size_override("font_size", 20)
	title_label.add_theme_color_override("font_color", Color.WHITE)
	title_bar.add_child(title_label)

	# 分隔
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_bar.add_child(spacer)

	# 關閉按鈕
	var close_btn := Button.new()
	close_btn.text = "✕"
	close_btn.custom_minimum_size = Vector2(30, 30)
	close_btn.pressed.connect(func(): close_requested.emit(); queue_free())
	title_bar.add_child(close_btn)
	main_vbox.add_child(title_bar)

	# ── 分頁列 ──
	var tab_bar := _make_hbox(35)
	tab_bar.add_theme_constant_override("separation", 4)
	var tabs := [
		{"id": "friends", "label": "👥 好友 (%d/%d)" % [social.get_online_count(), social.get_friend_count()]},
		{"id": "chat", "label": "💬 聊天"},
		{"id": "profile", "label": "👤 個人資料"},
		{"id": "rank", "label": "🏆 排位"},
	]
	for t in tabs:
		var btn := Button.new()
		btn.text = t["label"]
		btn.custom_minimum_size = Vector2(150, 30)
		var btn_style := StyleBoxFlat.new()
		btn_style.bg_color = Color(0.15, 0.15, 0.2)
		btn_style.corner_radius_top_left = 4
		btn_style.corner_radius_top_right = 4
		btn_style.corner_radius_bottom_left = 4
		btn_style.corner_radius_bottom_right = 4
		btn.add_theme_stylebox_override("normal", btn_style)
		var hover_style := StyleBoxFlat.new()
		hover_style.bg_color = Color(0.25, 0.25, 0.35)
		hover_style.corner_radius_top_left = 4
		hover_style.corner_radius_top_right = 4
		hover_style.corner_radius_bottom_left = 4
		hover_style.corner_radius_bottom_right = 4
		btn.add_theme_stylebox_override("hover", hover_style)
		btn.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
		btn.add_theme_font_size_override("font_size", 13)
		var tab_id: String = t["id"]
		btn.pressed.connect(func(): _switch_tab(tab_id))
		tab_bar.add_child(btn)
		tab_buttons[tab_id] = btn
	main_vbox.add_child(tab_bar)

	# ── 分隔線 ──
	var sep := HSeparator.new()
	sep.add_theme_constant_override("separation", 0)
	main_vbox.add_child(sep)

	# ── 內容區 ──
	var content := Control.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	main_vbox.add_child(content)

	# 好友列表
	friend_list_container = VBoxContainer.new()
	friend_list_container.set_anchors_preset(Control.PRESET_FULL_RECT)
	friend_list_container.add_theme_constant_override("separation", 2)
	var scroll_friends := ScrollContainer.new()
	scroll_friends.set_anchors_preset(Control.PRESET_FULL_RECT)
	scroll_friends.add_child(friend_list_container)
	content.add_child(scroll_friends)

	# 聊天
	var chat_panel := VBoxContainer.new()
	chat_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	chat_panel.visible = false
	content.add_child(chat_panel)

	# 頻道選擇
	var channel_bar := _make_hbox(30)
	for ch_name in ["global", "party", "team"]:
		var ch_btn := Button.new()
		ch_btn.text = {"global": "🌍 全服", "party": "🏠 群組", "team": "⚔ 隊伍"}[ch_name]
		ch_btn.custom_minimum_size = Vector2(80, 28)
		var ch: String = ch_name
		ch_btn.pressed.connect(func(): _switch_chat_channel(ch))
		channel_bar.add_child(ch_btn)
	chat_panel.add_child(channel_bar)

	# 聊天記錄
	chat_log = RichTextLabel.new()
	chat_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chat_log.bbcode_enabled = true
	chat_log.add_theme_color_override("default_color", Color(0.8, 0.8, 0.9))
	chat_panel.add_child(chat_log)

	# 輸入列
	var input_bar := _make_hbox(32)
	chat_input = LineEdit.new()
	chat_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	chat_input.placeholder_text = "輸入訊息..."
	chat_input.text_submitted.connect(_on_chat_submit)
	input_bar.add_child(chat_input)
	var send_btn := Button.new()
	send_btn.text = "發送"
	send_btn.pressed.connect(func(): _on_chat_submit(chat_input.text))
	input_bar.add_child(send_btn)
	chat_panel.add_child(input_bar)

	# 個人資料
	profile_container = VBoxContainer.new()
	profile_container.set_anchors_preset(Control.PRESET_FULL_RECT)
	profile_container.visible = false
	content.add_child(profile_container)

	# 排位
	rank_container = VBoxContainer.new()
	rank_container.set_anchors_preset(Control.PRESET_FULL_RECT)
	rank_container.visible = false
	content.add_child(rank_container)

	# 存取聊天面板
	tab_buttons["chat_panel"] = chat_panel


func _switch_tab(tab_id: String) -> void:
	current_tab = tab_id
	# 隱藏所有內容
	friend_list_container.get_parent().get_parent().get_child(1).visible = false
	tab_buttons.get("chat_panel", null).visible = false
	profile_container.visible = false
	rank_container.visible = false

	match tab_id:
		"friends":
			_build_friends_list()
			friend_list_container.get_parent().get_parent().get_child(1).visible = true
		"chat":
			tab_buttons.get("chat_panel", null).visible = true
			_refresh_chat()
		"profile":
			_build_profile()
			profile_container.visible = true
		"rank":
			_build_rank()
			rank_container.visible = true


func _build_friends_list() -> void:
	# 清空
	for c in friend_list_container.get_children():
		c.queue_free()

	# 好友邀請
	if social.friend_requests.size() > 0:
		var req_label := Label.new()
		req_label.text = "── 好友邀請 (%d) ──" % social.friend_requests.size()
		req_label.add_theme_color_override("font_color", Color(1.0, 0.8, 0.0))
		req_label.add_theme_font_size_override("font_size", 14)
		friend_list_container.add_child(req_label)

		for req in social.friend_requests:
			var row := _make_friend_row(req, true)
			friend_list_container.add_child(row)

	# 在線好友
	var online_label := Label.new()
	online_label.text = "── 在線 (%d) ──" % social.get_online_count()
	online_label.add_theme_color_override("font_color", Color(0.0, 1.0, 0.5))
	online_label.add_theme_font_size_override("font_size", 14)
	friend_list_container.add_child(online_label)

	for f in social.friends:
		if f["online"]:
			var row := _make_friend_row(f, false)
			friend_list_container.add_child(row)

	# 離線好友
	var offline_count: int = social.friends.size() - social.get_online_count()
	if offline_count > 0:
		var offline_label := Label.new()
		offline_label.text = "── 離線 (%d) ──" % offline_count
		offline_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
		offline_label.add_theme_font_size_override("font_size", 14)
		friend_list_container.add_child(offline_label)

		for f in social.friends:
			if not f["online"]:
				var row := _make_friend_row(f, false)
				friend_list_container.add_child(row)


func _make_friend_row(friend: Dictionary, is_request: bool) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 48)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.12, 0.12, 0.18) if not is_request else Color(0.15, 0.12, 0.05)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 4
	style.content_margin_bottom = 4
	panel.add_theme_stylebox_override("panel", style)

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 10)
	panel.add_child(hbox)

	# 狀態指示燈
	var dot := ColorRect.new()
	dot.custom_minimum_size = Vector2(8, 8)
	dot.color = Color(0.0, 1.0, 0.5) if friend.get("online", false) else Color(0.4, 0.4, 0.4)
	hbox.add_child(dot)

	# 名稱
	var name_label := Label.new()
	name_label.text = friend.get("name", "Unknown")
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", Color.WHITE if friend.get("online", false) else Color(0.5, 0.5, 0.6))
	hbox.add_child(name_label)

	# 段位
	var rank_label := Label.new()
	var tier: int = friend.get("rank", 0)
	var div: int = friend.get("division", 1)
	rank_label.text = social.get_rank_name(tier, div)
	rank_label.add_theme_font_size_override("font_size", 12)
	rank_label.add_theme_color_override("font_color", social.get_rank_color(tier))
	hbox.add_child(rank_label)

	# 狀態文字
	var status_label := Label.new()
	status_label.text = friend.get("last_seen", "")
	status_label.add_theme_font_size_override("font_size", 11)
	status_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
	hbox.add_child(status_label)

	# 按鈕區
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)

	if is_request:
		var accept_btn := Button.new()
		accept_btn.text = "✓ 接受"
		accept_btn.custom_minimum_size = Vector2(60, 26)
		var friend_id: String = friend["id"]
		accept_btn.pressed.connect(func(): social.accept_friend(friend_id); _build_friends_list())
		hbox.add_child(accept_btn)

		var decline_btn := Button.new()
		decline_btn.text = "✗ 拒絕"
		decline_btn.custom_minimum_size = Vector2(60, 26)
		decline_btn.pressed.connect(func(): social.decline_friend(friend_id); _build_friends_list())
		hbox.add_child(decline_btn)
	else:
		# 邀請按鈕
		var invite_btn := Button.new()
		invite_btn.text = "邀请组队"
		invite_btn.custom_minimum_size = Vector2(70, 26)
		hbox.add_child(invite_btn)

		# 更多選項
		var more_btn := Button.new()
		more_btn.text = "⋯"
		more_btn.custom_minimum_size = Vector2(26, 26)
		hbox.add_child(more_btn)

	return panel


func _switch_chat_channel(channel: String) -> void:
	chat_channel = channel
	_refresh_chat()


func _refresh_chat() -> void:
	if chat_log == null:
		return
	chat_log.clear()
	var messages: Array = social.get_messages(chat_channel, 50)
	for msg in messages:
		var sender: String = msg.get("sender", "")
		var text: String = msg.get("message", "")
		var color := Color(0.0, 1.0, 0.5) if sender == "SYSTEM" else Color(0.3, 0.7, 1.0) if sender == "thumb" else Color(0.8, 0.8, 0.9)
		chat_log.append_text("[color=#%s]%s[/color]: %s\n" % [color.to_html(false), sender, text])


func _on_chat_submit(text: String) -> void:
	if text.strip_edges().is_empty():
		return
	social.send_message(chat_channel, text)
	chat_input.text = ""
	_refresh_chat()


func _build_profile() -> void:
	for c in profile_container.get_children():
		c.queue_free()

	var scroll := ScrollContainer.new()
	scroll.set_anchors_preset(Control.PRESET_FULL_RECT)
	profile_container.add_child(scroll)

	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 12)
	scroll.add_child(vbox)

	# 標題
	var header := Label.new()
	header.text = "── 個人資料 ──"
	header.add_theme_font_size_override("font_size", 18)
	header.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(header)

	# 玩家名
	var name_card := _make_stat_card("玩家名", "thumb", Color(0.3, 0.7, 1.0))
	vbox.add_child(name_card)

	# 段位
	var rank_card := _make_stat_card("當前段位", social.get_rank_name(), social.get_rank_color())
	vbox.add_child(rank_card)

	# KDA
	var kda: Dictionary = social.get_kda()
	var kda_card := _make_stat_card("KDA", kda["display"], Color.WHITE)
	vbox.add_child(kda_card)

	# 勝率
	var win_rate: float = social.get_win_rate()
	var wr_card := _make_stat_card("勝率", "%.1f%% (%d勝 %d敗)" % [win_rate, social.stats["matches_won"], social.stats["matches_lost"]], Color(0.0, 1.0, 0.5) if win_rate >= 50 else Color(1.0, 0.3, 0.3))
	vbox.add_child(wr_card)

	# 對戰場數
	var matches_card := _make_stat_card("對戰場數", str(social.stats["matches_played"]), Color.WHITE)
	vbox.add_child(matches_card)

	# 連勝
	var streak_card := _make_stat_card("當前連勝", str(social.stats["win_streak"]), Color(1.0, 0.85, 0.0) if social.stats["win_streak"] > 0 else Color(0.5, 0.5, 0.6))
	vbox.add_child(streak_card)

	# 最佳連勝
	var best_card := _make_stat_card("最佳連勝", str(social.stats["best_win_streak"]), Color(1.0, 0.85, 0.0))
	vbox.add_child(best_card)

	# 爆頭率
	var hs_rate := 0.0
	if social.stats["kills"] > 0:
		hs_rate = float(social.stats["headshots"]) / float(social.stats["kills"]) * 100.0
	var hs_card := _make_stat_card("爆頭率", "%.1f%%" % hs_rate, Color(1.0, 0.5, 0.2))
	vbox.add_child(hs_card)

	# 最近對戰歷史
	var hist_label := Label.new()
	hist_label.text = "── 最近對戰 ──"
	hist_label.add_theme_font_size_override("font_size", 16)
	hist_label.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(hist_label)

	var history: Array = social.stats.get("match_history", [])
	var recent := history.slice(-5)
	recent.reverse()
	for match in recent:
		var match_card := _make_match_card(match)
		vbox.add_child(match_card)


func _make_stat_card(label_text: String, value_text: String, value_color: Color) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 40)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.1, 0.1, 0.15)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	panel.add_theme_stylebox_override("panel", style)

	var hbox := HBoxContainer.new()
	panel.add_child(hbox)

	var label := Label.new()
	label.text = label_text
	label.add_theme_font_size_override("font_size", 13)
	label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.7))
	hbox.add_child(label)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(spacer)

	var value := Label.new()
	value.text = value_text
	value.add_theme_font_size_override("font_size", 14)
	value.add_theme_color_override("font_color", value_color)
	hbox.add_child(value)

	return panel


func _make_match_card(match_data: Dictionary) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(0, 36)
	var style := StyleBoxFlat.new()
	var is_win: bool = match_data.get("result", "") == "win"
	style.bg_color = Color(0.05, 0.12, 0.05) if is_win else Color(0.12, 0.05, 0.05)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	style.content_margin_left = 10
	style.content_margin_right = 10
	style.content_margin_top = 4
	style.content_margin_bottom = 4
	panel.add_theme_stylebox_override("panel", style)

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	panel.add_child(hbox)

	# 結果
	var result_label := Label.new()
	result_label.text = "勝" if is_win else "敗"
	result_label.add_theme_font_size_override("font_size", 13)
	result_label.add_theme_color_override("font_color", Color(0.0, 1.0, 0.5) if is_win else Color(1.0, 0.3, 0.3))
	hbox.add_child(result_label)

	# 比分
	var score_label := Label.new()
	score_label.text = match_data.get("score", "?-?")
	score_label.add_theme_font_size_override("font_size", 13)
	score_label.add_theme_color_override("font_color", Color.WHITE)
	hbox.add_child(score_label)

	# KDA
	var kda_label := Label.new()
	kda_label.text = match_data.get("kda", "0/0/0")
	kda_label.add_theme_font_size_override("font_size", 12)
	kda_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
	hbox.add_child(kda_label)

	# 地圖
	var map_label := Label.new()
	map_label.text = match_data.get("map", "未知")
	map_label.add_theme_font_size_override("font_size", 11)
	map_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
	hbox.add_child(map_label)

	# 模式
	var mode_label := Label.new()
	mode_label.text = match_data.get("mode", "一般")
	mode_label.add_theme_font_size_override("font_size", 11)
	mode_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
	hbox.add_child(mode_label)

	# Agent
	var agent_label := Label.new()
	agent_label.text = match_data.get("agent", "?")
	agent_label.add_theme_font_size_override("font_size", 11)
	agent_label.add_theme_color_override("font_color", Color(0.3, 0.7, 1.0))
	hbox.add_child(agent_label)

	return panel


func _build_rank() -> void:
	for c in rank_container.get_children():
		c.queue_free()

	var scroll := ScrollContainer.new()
	scroll.set_anchors_preset(Control.PRESET_FULL_RECT)
	rank_container.add_child(scroll)

	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vbox.add_theme_constant_override("separation", 16)
	scroll.add_child(vbox)

	# 段位顯示
	var rank_card := PanelContainer.new()
	rank_card.custom_minimum_size = Vector2(0, 120)
	var rank_style := StyleBoxFlat.new()
	rank_style.bg_color = Color(0.08, 0.08, 0.12)
	rank_style.corner_radius_top_left = 8
	rank_style.corner_radius_top_right = 8
	rank_style.corner_radius_bottom_left = 8
	rank_style.corner_radius_bottom_right = 8
	rank_style.content_margin_left = 20
	rank_style.content_margin_right = 20
	rank_style.content_margin_top = 16
	rank_style.content_margin_bottom = 16
	rank_card.add_theme_stylebox_override("panel", rank_style)
	vbox.add_child(rank_card)

	var rank_vbox := VBoxContainer.new()
	rank_vbox.add_theme_constant_override("separation", 8)
	rank_card.add_child(rank_vbox)

	# 段位名稱
	var rank_name_label := Label.new()
	rank_name_label.text = social.get_rank_name()
	rank_name_label.add_theme_font_size_override("font_size", 28)
	rank_name_label.add_theme_color_override("font_color", social.get_rank_color())
	rank_name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank_vbox.add_child(rank_name_label)

	# RP 顯示
	var rp_label := Label.new()
	rp_label.text = "RP: %d / 100" % social.rank_points
	rp_label.add_theme_font_size_override("font_size", 16)
	rp_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.8))
	rp_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank_vbox.add_child(rp_label)

	# 進度條
	var progress_bar := ProgressBar.new()
	progress_bar.custom_minimum_size = Vector2(300, 12)
	progress_bar.max_value = 100
	progress_bar.value = social.rank_points
	progress_bar.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	var prog_style := StyleBoxFlat.new()
	prog_style.bg_color = Color(0.15, 0.15, 0.2)
	prog_style.corner_radius_top_left = 6
	prog_style.corner_radius_top_right = 6
	prog_style.corner_radius_bottom_left = 6
	prog_style.corner_radius_bottom_right = 6
	progress_bar.add_theme_stylebox_override("background", prog_style)
	var fill_style := StyleBoxFlat.new()
	fill_style.bg_color = social.get_rank_color()
	fill_style.corner_radius_top_left = 6
	fill_style.corner_radius_top_right = 6
	fill_style.corner_radius_bottom_left = 6
	fill_style.corner_radius_bottom_right = 6
	progress_bar.add_theme_stylebox_override("fill", fill_style)
	rank_vbox.add_child(progress_bar)

	# 賽季資訊
	var season_label := Label.new()
	season_label.text = "賽季 %d" % social.season
	season_label.add_theme_font_size_override("font_size", 12)
	season_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
	season_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank_vbox.add_child(season_label)

	# 排位統計
	var stats_header := Label.new()
	stats_header.text = "── 排位統計 ──"
	stats_header.add_theme_font_size_override("font_size", 16)
	stats_header.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(stats_header)

	var win_rate: float = social.get_win_rate()
	vbox.add_child(_make_stat_card("勝率", "%.1f%%" % win_rate, Color(0.0, 1.0, 0.5) if win_rate >= 50 else Color(1.0, 0.3, 0.3)))
	vbox.add_child(_make_stat_card("對戰場數", str(social.stats["matches_played"]), Color.WHITE))
	vbox.add_child(_make_stat_card("最佳連勝", str(social.stats["best_win_streak"]), Color(1.0, 0.85, 0.0)))

	# 排位歷史
	var hist_header := Label.new()
	hist_header.text = "── 排位歷史 ──"
	hist_header.add_theme_font_size_override("font_size", 16)
	hist_header.add_theme_color_override("font_color", Color.WHITE)
	vbox.add_child(hist_header)

	var rank_history: Array = social.rank_history.slice(-10)
	rank_history.reverse()
	for entry in rank_history:
		var entry_panel := PanelContainer.new()
		entry_panel.custom_minimum_size = Vector2(0, 32)
		var entry_style := StyleBoxFlat.new()
		entry_style.bg_color = Color(0.1, 0.1, 0.15)
		entry_style.corner_radius_top_left = 4
		entry_style.corner_radius_top_right = 4
		entry_style.corner_radius_bottom_left = 4
		entry_style.corner_radius_bottom_right = 4
		entry_style.content_margin_left = 10
		entry_style.content_margin_right = 10
		entry_style.content_margin_top = 4
		entry_style.content_margin_bottom = 4
		entry_panel.add_theme_stylebox_override("panel", entry_style)

		var hbox := HBoxContainer.new()
		hbox.add_theme_constant_override("separation", 12)
		entry_panel.add_child(hbox)

		var result_label := Label.new()
		var is_win: bool = entry.get("result", "") == "win"
		result_label.text = "勝" if is_win else "敗"
		result_label.add_theme_font_size_override("font_size", 12)
		result_label.add_theme_color_override("font_color", Color(0.0, 1.0, 0.5) if is_win else Color(1.0, 0.3, 0.3))
		hbox.add_child(result_label)

		var rp_label2 := Label.new()
		var rp_change: int = entry.get("rp_change", 0)
		rp_label2.text = "%+d RP" % rp_change
		rp_label2.add_theme_font_size_override("font_size", 12)
		rp_label2.add_theme_color_override("font_color", Color(0.0, 1.0, 0.5) if rp_change > 0 else Color(1.0, 0.3, 0.3))
		hbox.add_child(rp_label2)

		var date_label := Label.new()
		date_label.text = entry.get("date", "")
		date_label.add_theme_font_size_override("font_size", 11)
		date_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.6))
		hbox.add_child(date_label)

		vbox.add_child(entry_panel)


func _make_hbox(separation: int = 8) -> HBoxContainer:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", separation)
	return hbox
