"""Stage I: merge kk (first) then en voiceover/captions into canonical.json.

Source texts only — no numbers are invented here; verify_i.py proves digit
parity across ru/kk/en afterwards. Bumps canonical version 1 -> 2.
"""

import json
from pathlib import Path

ROOT = Path(r"C:\Users\sunak\Projects\aetherlab")
CANON = ROOT / "output" / "stage_f_content" / "canonical.json"

KK = {
    # block_id: (voiceover, [captions])
    "B0": ("Мәшине секундына екі метр жылдамдықпен келе жатыр және бірқалыпты үдейді. "
           "Төрт секундтан кейін жылдамдық он төрт метр секундқа жетеді. "
           "Ол қанша метр жүрді? Сабақ соңында жауапты екі тәсілмен табасың.",
           ["Мәшине қанша метр жүрді?", "Жауап — екі тәсілмен"]),
    "B1": ("Егер жылдамдық өзгермесе — қозғалыс бірқалыпты: v тең s бөлінген t. "
           "Бізде жылдамдық өседі — бірақ әр секундта бірдей шамаға өседі. "
           "Әр секундта жылдамдық секундына үш метрге артады — бұл үдеудің үшке тең екенін білдіреді. "
           "Мұндай қозғалыс теңүдемелі деп аталады. "
           "Жылдамдықтың өсу шапшаңдығын үдеу көрсетеді: a тең жылдамдық өзгерісін уақытқа бөлгенге. "
           "Өлшем бірлігі — метр секундына квадрат. "
           "Икс осін қозғалыс бағытымен бағыттаймыз: алға бағытталғанның бәрі плюс таңбасымен.",
           ["v = s / t — бірқалыпты", "a = Δv / Δt", "[a] = м/с²", "Ox осі →"]),
    "B2": ("Кез келген сәттегі жылдамдық — бастапқы жылдамдық пен өсімшенің қосындысы. "
           "Өсімше — үдеу мен уақыттың көбейтіндісі: v тең v нөл плюс a t. "
           "Сандарды қоямыз: екі плюс үш көбейту төрт — секундына он төрт метр. "
           "Бірліктерді тексер: метр секундына квадратты секундқа көбейткенде метр секунд шығады. Бәрі сәйкес.",
           ["v = v₀ + at", "2 + 3·4 = 14 м/с"]),
    "B3": ("Орын ауыстыру — дененің старттан қанша ығысқаны. "
           "Бағыт өзгермесе, ол жүрілген жолға тең. "
           "Формула: s тең v нөл t плюс a t квадраттың жартысы. "
           "Бірінші қосылғыш — үдемей жүрген жол, екіншісі — үдеуден қосылғаны. "
           "Есептейміз: екі көбейту төрт — сегіз, плюс үш көбейту он алтының жартысы — жиырма төрт. "
           "Барлығы отыз екі метр.",
           ["s = v₀t + at²/2", "8 + 24 = 32 м", "бағыт өзгермейді"]),
    "B4": ("Жылдамдықтың уақытқа тәуелділік графигін саламыз: v тең екі плюс үш t. "
           "Бұл түзу: нөлде — екі, төрт секундтан кейін — он төрт. "
           "Түзудің көлбеуі — бұл үдеу: неғұрлым тік болса, a соғұрлым үлкен. "
           "Есте сақта: v-ның t-ға тәуелділік графигінің көлбеуі үдеуге тең.",
           ["v = 2 + 3t", "көлбеу = a"]),
    "B5": ("Енді тексереміз. Жылдамдық графигі астындағы аудан сан жағынан орын ауыстыруға тең. "
           "Бізде табандары екі мен он төрт, биіктігі төрт трапеция: "
           "табандардың жарты қосындысын биіктікке көбейтеміз — сегіз көбейту төрт — отыз екі метр. "
           "Формуламен сәйкес келді. Екі тәсіл — бір жауап.",
           ["S = (2+14)/2 · 4 = 32 м", "аудан = орын ауыстыру ✓"]),
    "B6": ("Енді өзің. Мәшине орнынан секундына квадрат екі метр үдеумен қозғалды. "
           "Бес секундта қанша жол жүреді? Видеоны кідірте тұр да, өзің шығар. "
           "Жауабы: нөл көбейту бес плюс екі көбейту жиырма бестің жартысы — жиырма бес метр.",
           ["v₀ = 0, a = 2, t = 5, s = ?", "Кідірте тұр!", "s = 25 м"]),
    "B7": ("Екі қақпан. Біріншісі: соңғы жылдамдықты бірқалыпты қозғалыс формуласына қою: "
           "он төрт көбейту төрт — елу алты. Қате: жылдамдық өсіп отыр, орташасын алу керек. "
           "Екіншісі: көлбеу мен ауданды шатастыру. Көлбеу — бұл үдеу, аудан — орын ауыстыру. "
           "Қорытынды: v тең v нөл плюс a t; s тең v нөл t плюс a t квадраттың жартысы; "
           "v-ның t-ға графигі астындағы аудан — орын ауыстыру. "
           "График ауданына есептер ҰБТ байқау сынақтарында кездеседі — енді оларды танисың.",
           ["✗ 14·4 = 56", "көлбеу = a; аудан = s", "v = v₀ + at; s = v₀t + at²/2"]),
}

EN = {
    "B0": ("A car travels at two metres per second and accelerates smoothly. "
           "After four seconds it already does fourteen. How many metres did it cover? "
           "By the end of the lesson you will find the answer two ways.",
           ["How far did the car go?", "Two ways to the answer"]),
    "B1": ("If speed never changes, motion is uniform: v equals s over t. "
           "Here speed grows — but grows by the same amount each second. "
           "Every second adds three metres per second — that is what an acceleration of three means. "
           "Such motion is called uniformly accelerated. "
           "Acceleration measures how fast velocity grows: a equals the change in velocity divided by time. "
           "Its unit is the metre per second squared. "
           "We point the x axis along the motion: everything forward takes the plus sign.",
           ["v = s / t — uniform", "a = Δv / Δt", "[a] = m/s²", "x axis →"]),
    "B2": ("Velocity at any moment is the starting velocity plus the gain. "
           "The gain is acceleration times time: v equals v naught plus a t. "
           "Plug in our numbers: two plus three times four — fourteen metres per second. "
           "Check the units: metres per second squared times seconds gives metres per second. It all fits.",
           ["v = v₀ + at", "2 + 3·4 = 14 m/s"]),
    "B3": ("Displacement is how far the body shifted from the start. "
           "While direction stays the same, it equals the distance travelled. "
           "The formula: s equals v naught t plus a t squared over two. "
           "The first term is what we would cover without accelerating; the second is the boost from acceleration. "
           "Let's compute: two times four is eight, plus three times sixteen over two — twenty-four. "
           "Thirty-two metres in total.",
           ["s = v₀t + at²/2", "8 + 24 = 32 m", "direction unchanged"]),
    "B4": ("Let's plot velocity against time: v equals two plus three t. "
           "It is a straight line: two at zero, fourteen after four seconds. "
           "The slope of the line is the acceleration: the steeper, the larger the a. "
           "Remember: the slope of the v–t graph equals the acceleration.",
           ["v = 2 + 3t", "slope = a"]),
    "B5": ("Now the check. The area under the velocity graph numerically equals the displacement. "
           "We have a trapezoid with bases two and fourteen and height four: "
           "half the sum of the bases times the height — eight times four — thirty-two metres. "
           "It matches the formula. Two ways, one answer.",
           ["S = (2+14)/2 · 4 = 32 m", "area = displacement ✓"]),
    "B6": ("Now you. A car starts from rest with an acceleration of two metres per second squared. "
           "How far does it go in five seconds? Pause the video and solve it. "
           "Answer: zero times five plus two times twenty-five over two — twenty-five metres.",
           ["v₀ = 0, a = 2, t = 5, s = ?", "Pause!", "s = 25 m"]),
    "B7": ("Two traps. First: plugging the final speed into the uniform-motion formula: "
           "fourteen times four is fifty-six. Wrong: the speed was growing, you must take the average. "
           "Second: mixing up slope and area. Slope is acceleration; area is displacement. "
           "To sum up: v equals v naught plus a t; s equals v naught t plus a t squared over two; "
           "the area under the v–t graph is the displacement. "
           "Graph-area problems appear in UNT mocks — now you will recognise them.",
           ["✗ 14·4 = 56", "slope = a; area = s", "v = v₀ + at; s = v₀t + at²/2"]),
}

canon = json.loads(CANON.read_text(encoding="utf-8"))
assert canon["version"] == 1, canon["version"]
assert set(KK) == set(EN) == {b["id"] for b in canon["blocks"]}
for block in canon["blocks"]:
    voice_kk, caps_kk = KK[block["id"]]
    voice_en, caps_en = EN[block["id"]]
    assert len(caps_kk) == len(caps_en) == len(block["captions"]), block["id"]
    block["voiceover_kk"] = voice_kk
    block["voiceover_en"] = voice_en
    block["captions_kk"] = caps_kk
    block["captions_en"] = caps_en
canon["version"] = 2
canon["language_review_status"] = "auto_checked_teacher_review_pending"
CANON.write_text(json.dumps(canon, ensure_ascii=False, indent=1), encoding="utf-8")
print("canonical.json -> v2 with kk/en voiceover + captions")
