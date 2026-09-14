//! Protocol SerDe parity：decode → re-encode 必須還原 Python 位元組。
use std::fs;
use vanta_parity::protocol::*;


fn main() {
    let dir = env!("CARGO_MANIFEST_DIR");
    let data = fs::read(format!("{dir}/packets.bin")).expect("packets.bin 不存在");

    let mut o = 0usize;
    let mut n = 0u32;
    while o + 4 <= data.len() {
        let len = u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        o += 4;
        let pkt = &data[o..o + len];
        o += len;
        n += 1;

        let reencoded: Vec<u8> = if pkt[1] == TYPE_INPUT {
            InputPkt::decode(pkt).expect("INPUT decode 失敗").encode().to_vec()
        } else if pkt[1] == TYPE_SNAPSHOT {
            SnapshotPkt::decode(pkt).expect("SNAPSHOT decode 失敗").encode()
        } else if pkt[1] == TYPE_WELCOME {
            WelcomePkt::decode(pkt).expect("WELCOME decode 失敗").encode().to_vec()
        } else if pkt[1] == TYPE_GAME_EVENT {
            GameEventPkt::decode(pkt).expect("GAME_EVENT decode 失敗").encode().to_vec()
        } else if pkt[1] == TYPE_MATCH_STATE {
            MatchStatePkt::decode(pkt).expect("MATCH_STATE decode 失敗").encode().to_vec()
        } else {
            panic!("未知封包型別 {}", pkt[1]);
        };
        assert_eq!(reencoded, pkt, "封包 #{n}（type={}）re-encode 與原始位元組不一致", pkt[1]);
    }

    println!("✅ PROTOCOL PARITY OK — {n} 個封包 decode→re-encode 位元組一致（INPUT/SNAPSHOT/WELCOME/GAME_EVENT）");
}
