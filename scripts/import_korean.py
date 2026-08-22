"""Write the three official Korean translations into song_translations.korean.

Mapping keys are the exact app lyric sentences; values are the Korean
translation shown for that sentence.
"""

from __future__ import annotations

import sqlite3

DB = r"app\src\main\assets\translated.db"

KOREAN = {
    "Maharajah": {
        "O Skaid Minelu Minelia Oh Di": "천문대, 천랑성, 거울 속 달",
        "Hellm a Cat Galha Sol end Xia Rata": "환상의 고양이는 쓸쓸한 미소를 남기곤 사라져 버렸다",
        "End Droq Kre Di Escolia": "가방, 맨발, 투명한 장례식",
        "Alvete Drone a Noll Sar Linq End Elay Elie Bis ah": "고독한 세계에 온 것을 환영해, 모두가 그렇게 이곳에 도착했어",
        "Hal a Story Oracle end": "“옛날이야기를 해보자”",
        "Ani Brait Door len Razzle em Carafe": "열린 문, 떨어져 깨지는 카라페",
        "Ah Mail Shiita end a Fete": "천명을 걸치고 운명을 구가해봐",
        "ah Cate Aola Crai Lamiy end Shelista Hal a Olkei Mii": "너는 지금 살아있고, 세상에서 가장 옳은 사람이야",
        "Ay Mii end Harmiy": "“잠깐 기다려! 그건 너무 지나쳐!”",
        "a Xia Trico": "“잠깐 기다려! 그건 너무 지나쳐!”",
        "Bllink Asta Ya Historia ou Leat ah Coffee": "깜빡이는 빛, 쓰이는 역사, 놓인 커피",
        "Dist far Age Winde Bis lan la Nouche ou Crai Bai Dis Harie Ya": "“눈을 떴어?” 여기는 너의 밤이야, 벌써 잊어버렸어?",
        "Leste Hal a Story Oracle end": "“옛날이야기를 해보자”",
        "Ani Brait Door end Razzle Carafe": "열린 문, 떨어져 깨진 카라페",
        "Ah Mii o Xia hellm Story Foul Talis end ah Talis": "아, 그건 어디선가 들어본 적이 있는 이야기야. 아주 아주 오래전에...",
        "Dist far Age Winde Bis lan la": "“눈을 떴어?” 여기는 너의 밤이야, 벌써 잊어버렸어?",
        "Mii Herz Jam a Giinia Trane": "고뇌하는 마음과 금빛 눈물",
        "Kre end a Lane Ary Wolme ou Historia": "맨발인 채로 고문서의 융단 위를 뛰어라",
        "Liix Mage end Oracle Flasche": "용서의 마법과 기적의 유리병",
        "Mii Harmiy a Crai Shelta Foul": "“너라면 분명 괜찮을 거야”",
        "Bis Nacc Finz end Nouche ou Finz Dis": "이것은 끝, 끝나지 않는 밤의 끝",
        "Aihel end Age Alvete a Drone": "봐, 고독이 여기 있어",
        "Lai La Crai Bai Dis Harie Ya": "아니면 벌써 잊어버린 거야?",
    },
    "A Little Servant": {
        "Hellmeila Hellmeila Lar imm Miis Mols": "트로이메라이 트로이메라이 내게만 들리는 피날레",
        "Finzo a Fiola end ol Melnaid": "시든 꽃, 붉은 드레스, 커다란 소파, 성벽, 쇠창살, 어질러진 옷장, 깨어진 손톱",
        "Veit Syarfi Oul Solien Vala ou Quondlea": "시든 꽃, 붉은 드레스, 커다란 소파, 성벽, 쇠창살, 어질러진 옷장, 깨어진 손톱",
        "Jiddle Ceeka Meisem Clooshela": "시든 꽃, 붉은 드레스, 커다란 소파, 성벽, 쇠창살, 어질러진 옷장, 깨어진 손톱",
        "Klautie end ol Dizzle": "시든 꽃, 붉은 드레스, 커다란 소파, 성벽, 쇠창살, 어질러진 옷장, 깨어진 손톱",
        "Hellmeila Hellmeila Ah Salie Proula": "트로이메라이 트로이메라이 아아, 사제님",
        "Foul Xia o Siala end Dilem no Amie": "그건 분명 사랑이 없는 노래 누굴 위한 노래야?",
        "a Siala Blem lar o Shelista Plentie": "그건 분명 사랑이 없는 노래 누굴 위한 노래야?",
        "Cloud o Iequim Lef Mono": "이 세계는 영사기? 당신은 마치 모노크롬 같아",
        "Porta end Flous imm Hellm Olis Dooom Meele": "환상 위에 뜬 배, 아주 깊은 바다",
        "ol Eem Ra Voi Kulu Awter Shellius imm Selaf": "실은 신도 만날 수 있을 거 같았어",
        "Gout Hellm o Ola Poul ail": "하지만 환상은 결국 텅 비어있어",
        "Ignai Canvie Imeila Prous Amalait": "얼마나 간절히 기도해 봤자 말이야",
        "Yiep Wely il Kolto ou Tehomea": "심연의 밑바닥으로 가라앉아버려",
        "Qleel Mii Verse Lef Kulu Nai Harie Zel osa": "아무것도 떠올리지 못하도록 사라져 버릴까",
        "Yiep Wely Poetolt Heipe Sole ou Venesene": "망령을 끌어안고 가라앉아버려",
        "Qleel Mii Verse Iequim Lef Nai Aihel folme Talis": "처음부터 없었던 것처럼 사라져 버릴까",
        "Mii Qleea Spai imm Meele ou Trane": "눈물이 멈추질 않아",
        "Eilent Rave o Xia Haol Cloud Telly il Mii Selaf Note": "분함이 번져가 | 내밀어준 그 손은 진짜야?",
        "Kulu Nai Ranya end Kulu Nai Prifiel Zel Note": "아무것도 볼 수 없어 아무것도 알 수 없어",
        "Hiele Shellius Yiep Leimy Bai": "신이시여, 그만 놓아줘요",
        "Yiela Prous il Kolto ou Tehomea": "심연의 밑바닥에서 기도하소서",
        "Lef Feikeed end Piikle Xaite Herches": "그 심장을 찔러버리듯이",
        "Yiela Sween Poetolt Heipe Sole ou Venesene": "망령을 끌어안고 잠드소서",
        "Lef Yien Leimy folme Vins Hellm imm Lootaria": "영원한 악몽에서 벗어나듯이",
        "Hiele Meele ou Trane Farla": "보라, 바닥은 눈물의 바다 시들지 않는 바다",
        "imm Kolto Xia Ignai Dialoss": "보라, 바닥은 눈물의 바다 시들지 않는 바다",
    },
    "エリシアンズ・オールドマンズ(Elysion's Old Mans)": {
        "Grend Grend Walhalla ou Grend": "정의의 정의의 정의의 발할라",
        "Meeti Meeti Meeti Skyar Enes": "국경 국경 국경 따르는 사람들",
        "Eala Eala Eala Aka Prii": "떨어지는 떨어지는 떨어지는 물방울",
        "Melart Nai Iar Zel Pray": "“미안해요! 아무것도 들리질 않아요”",
        "Efok Efok Efok Poet nai Olte": "콜록 콜록 콜록 신경 쓰지 마",
        "Meeti Meeti Meeti Morhe Enes": "국경 국경 국경 애도하는 사람들",
        "Eala Eala Eala Heela Prii": "떨어지는 떨어지는 떨어지는 링거",
        "Melart Mii Nai Guit Zel Note": "“미안해요! 전 아무것도 모릅니다”",
        "Will a Shellarm Fiolaza a Herches": "고동과 신전, 꽃다발과 심장",
        "Arupe Elled Nols end ol Kllea end ol Sjiyupe": "고대의 엘리베이터, 잊어버린 물건, 울었던 숫자, 낙심한 숫자",
        "Grend imm Bis Lanai o Di Toup": "- 이 낙원에 있는 정의는 두 가지 -",
        "imm Herz a Ajarla Yien Alista": "소중히 품은 그 정의와 지금부터 만들어질 정의",
        "Kleet Kleet Kleet Og Perte": "대각선 대각선 대각선 서로 노려보고 있는 건",
        "Diazz Diazz Diazz Voi o Selaf": "쌍둥이 쌍둥이 쌍둥이, 진실일지도 모르겠네",
        "Capite Capite Taz Capite Scteus": "수도의 수도의 수도의 수호신이 잠든다면",
        "Sween Lishe Senju Elie Finza": "출구까지 출구까지 출구까지 데려다줄게",
        "Efa Efa Efa Hierti": "시대는 시대는 시대는 반복돼",
        "Oll Oll Oll Guit imm Selaf": "모두 모두 모두 사실은 알고 있지?",
    },
}


def main() -> None:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    updated = 0
    missing = []
    for song_title, mapping in KOREAN.items():
        for sentence, korean in mapping.items():
            cur.execute(
                "UPDATE song_translations SET korean = ? "
                "WHERE song_title = ? AND sentence = ?",
                (korean, song_title, sentence),
            )
            if cur.rowcount:
                updated += 1
            else:
                missing.append((song_title, sentence))
    conn.commit()
    print(f"已更新 {updated} 条韩译。")
    if missing:
        print("未匹配到的句子：")
        for song_title, sentence in missing:
            print(f"  [{song_title}] {sentence}")
    print("韩译总数：", cur.execute(
        "SELECT COUNT(*) FROM song_translations WHERE korean <> ''"
    ).fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
