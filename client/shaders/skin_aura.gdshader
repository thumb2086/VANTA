shader_type spatial;
// 槍身「能量紋」疊加層（作為 StandardMaterial3D 的 next_pass 使用）。
// 只畫沿花紋脊線流動的光，配合 albedo/emissive 貼圖 → 高級皮的「活起來」感。
// 若缺失此檔案，SkinMaterial 會自動退回純 StandardMaterial3D（不會報錯）。
render_mode blend_add, unshaded, cull_back, depth_draw_never, diffuse_burley, specular_schlick_ggx;

uniform sampler2D pattern : filter_linear_mipmap, repeat_enable;
uniform vec4 glow_color : source_color = vec4(1.0, 0.62, 0.30, 1.0);
uniform float intensity = 0.75;
uniform float flow_speed = 0.25;
uniform float pulse_speed = 1.15;
uniform float uv_scale = 1.6;
uniform float band_width = 0.30;
uniform float edge_power = 1.8;

varying vec2 uv_x;
varying vec3 nrm_x;
varying vec3 pos_x;

void vertex() {
	uv_x = UV;
	nrm_x = NORMAL;
	pos_x = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = uv_x * uv_scale;
	// 花紋亮度場 + 緩慢流動 → 取得「紋路」輪廓
	float base = texture(pattern, uv + vec2(TIME * flow_speed * 0.35, 0.0)).r;
	float ridge = texture(pattern, uv - vec2(TIME * flow_speed * 0.18, TIME * flow_speed * 0.07)).g;
	float field = clamp(base * 0.65 + ridge * 0.45, 0.0, 1.0);

	// 移動的掃描帶（開槍後短暫增強：由 TIME 週期驅動）
	float scan = fract(field * 2.2 - TIME * flow_speed * 0.9);
	float band = pow(1.0 - abs(scan * 2.0 - 1.0), 1.0 / max(0.02, band_width));

	// 脈動 + 視角邊緣（Fresnel）→ 邊緣發亮、正面克制
	float pulse = 0.72 + 0.28 * sin(TIME * pulse_speed + field * 6.283);
	vec3 view_dir = normalize(-VIEW);
	float fres = pow(1.0 - clamp(dot(normalize(nrm_x), view_dir), 0.0, 1.0), 2.0);

	float amt = (band * 0.55 + pow(field, edge_power) * 0.55) * pulse * (0.35 + fres * 1.35);
	amt = clamp(amt, 0.0, 1.0) * intensity;

	ALBEDO = glow_color.rgb * amt;
	ALPHA = 1.0;
}
