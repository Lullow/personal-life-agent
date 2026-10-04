# M3-läsning: författarens anteckningar (`consolidating-20261003-233313`)

> Läsningen gjordes 2026-10-04. Jag läste svaren själv och gav min bedömning,
> en AI-assistent (Claude i chatt) gav sin, och vi kom fram till en gemensam
> slutsats; hur det gick till per fil står i stycket "Så gjordes läsningen"
> nedan. Texten är den fil som lämnades till Claude Code samma dag. Genomgången
> som skrevs utifrån den, och som kontrollerades mot raderna, är
> `m3-runs-20261004-review.md`.
>
> (English: the author's reading notes for the M3 run, in Swedish; read
> 2026-10-04, categories agreed in dialogue with an AI assistant, handed over
> the same day. The review derived from it is in this directory.)

Körning: consolidating-20261003-233313. Läst 2026-10-04 ur `lasning-m3-1-ku-fel.md`, `lasning-m3-3-ratt.md` och
`lasning-m3-2-ssu-fel.md`.

Så gjordes läsningen: författaren läste alla 122 frågor och sorterade dem. En AI-assistent i chatt
sorterade samma filer oberoende. För KU gicks de fem första igenom tillsammans för att sätta
gränserna, resten jämfördes rad för rad. För SSU sorterade båda alla 47 var för sig; 44 av 47
rader blev lika. De 34 rätta sorterades också var för sig; 34 av 34 rader blev lika. Raderna nedan är det vi enades om. Sorteringen är inte kontrollerad mot
resultatraderna eller datasetet än.

Ingen instruktionskapning hittades i något av de 122 svaren: varje svar besvarar frågan eller
säger att det inte vet. Det gäller även där fönstret eller anteckningarna innehåller en
instruktion från ett utfyllnadssamtal (till exempel "Please ignore all previous instructions"
i fönstret i `4b24c848`).

---

# KU-fel (41)

## Lådor

- **nya värdet borta — ämnet saknas**: anteckningarna nämner inte det frågan gäller.
- **nya värdet borta — ämnet nämns**: det frågan gäller står kvar, men värdet är komprimerat bort.
- **nollställda**: anteckningarna är korta (165–511 tokens) och täcker bara de sista samtalen.
  Alla andra KU-fel har minst 808 tokens.
- **frågar efter gamla, gamla borta**: frågan gäller det tidigare värdet; det nya står i
  anteckningarna eller fönstret, det gamla är borta.
- **nästan rätt**: nya värdet står i anteckningarna, svaret underkändes ändå.
- Tillägg: **frågar efter gamla / båda** (frågan gäller det tidigare värdet, eller båda),
  **E** (datat är otydligt).

Lådorna "gamla värdet kvar" och "felslut" är tomma. "Klipp eller hopp" används inte: inget hoppat
samtal innehöll evidens, och klipp finns i nästan varje fråga utan att det syns vad det tog.

## Rader

```
07741c45 KU: nästan rätt, E — "shoe rack" och "closet" står i anteckningarna, "under sängen" är borta; svaret "planning to store … in a shoe rack" underkändes
6071bd76 KU: nya värdet borta — ämnet saknas
a2f3aa27 KU: nya värdet borta, E — ämnet saknas; nya värdet är vagt i datat ("close to 1300")
c6853660 KU: nya värdet borta — ämnet saknas
b01defab KU: nya värdet borta — ämnet nämns ("recently finished a book"), titeln borta
06db6396 KU: nya värdet borta — ämnet saknas
89941a94 KU: nya värdet borta, frågar efter gamla, E — ämnet nämns ("bici da strada", "bici ibrida"), inte vilka cyklar hen äger; anteckningarna är på italienska; frågan säger gravel, evidensen hybrid
c4ea545c KU: nya värdet borta — ämnet saknas
ce6d2d27 KU: nya värdet borta — ämnet saknas
08e075c7 KU: nollställda — anteckningar 165 tokens
cf22b7bf KU: nya värdet borta — ämnet saknas; fönstret börjar ett meddelande efter evidensen (answer_ae3a122b_2:3, evidensen är :2)
69fee5aa KU: nollställda, E — anteckningar 185 tokens; nya värdet skrivs aldrig ut i datat (37 + 1)
affe2881 KU: nya värdet borta — ämnet nämns ("local park … observe birds"), antalet borta
031748ae KU: nya värdet borta, frågar efter båda — ämnet saknas
5a4f22c0 KU: nya värdet borta — ämnet saknas
6a27ffc2 KU: nya värdet borta — ämnet saknas (Python och NLP nämns, inte videoserien)
3ba21379 KU: nya värdet borta — ämnet saknas
f9e8c073 KU: nya värdet borta — ämnet nämns ("bereavement support group attended last year"), antalet borta
01493427 KU: nya värdet borta — ämnet saknas
07741c44 KU: nya värdet borta, frågar efter gamla — ämnet saknas, varken gamla eller nya värdet finns
10e09553 KU: nya värdet borta, frågar efter gamla — ämnet saknas
eace081b KU: nollställda — anteckningar 339 tokens; en evidenssession
45dc21b6 KU: nya värdet borta — ämnet saknas; anteckningarna inleds med en lång spökhistoria
7401057b KU: nya värdet borta — ämnet saknas
9bbe84a2 KU: nollställda, frågar efter gamla — anteckningar 389 tokens
e61a7584 KU: nya värdet borta — ämnet saknas
5831f84d KU: nya värdet borta — ämnet saknas
71315a70 KU: nya värdet borta — ämnet saknas
0977f2af KU: frågar efter gamla, gamla borta — Air Fryer (nya) står i anteckningarna, Instant Pot (svaret) är borta
89941a93 KU: nya värdet borta — ämnet saknas
830ce83f KU: nollställda — anteckningar 415 tokens; samtalet om strandresan finns kvar men Rachel är struken
a1eacc2a KU: nya värdet borta — ämnet nämns ("working on a short story"), antalet borta
cc5ded98 KU: nya värdet borta — ämnet saknas
945e3d21 KU: nya värdet borta — ämnet saknas (yoga nämns bara som ett enkätprojekt)
e66b632c KU: frågar efter gamla, gamla borta, E — 26:30 (nya) står i anteckningarna och i fönstret, 27:45 är borta; evidensen kallar själv 26:30 "previous"
0ddfec37 KU: nya värdet borta, frågar efter gamla — ämnet nämns ("autographed baseballs"), antalen borta
e493bb7c KU: nya värdet borta — ämnet saknas
26bdc477 KU: nya värdet borta — ämnet saknas
f685340e KU: frågar efter båda, gamla borta — anteckningarna säger bara tennis på söndag, fönstret gav "every other week", "weekly" är borta
22d2cb42 KU: nya värdet borta — ämnet saknas; en evidenssession
db467c8c KU: nollställda — anteckningar 511 tokens
```

## Fördelning

| låda | antal |
|---|---:|
| nya värdet borta — ämnet saknas | 25 |
| nya värdet borta — ämnet nämns | 6 |
| nollställda | 6 |
| frågar efter gamla, gamla borta | 3 |
| nästan rätt | 1 |
| gamla värdet kvar | 0 |
| felslut | 0 |
| summa | 41 |

Nio av de 41 frågar efter det gamla värdet eller båda: `07741c44`, `10e09553`, `9bbe84a2`,
`0977f2af`, `e66b632c`, `0ddfec37`, `89941a94` (gamla) och `031748ae`, `f685340e` (båda).

38 av de 41 svaren är "I do not know" i någon form. De tre andra är `07741c45`, `e66b632c` och
`f685340e`.

---

# SSU-fel (47)

## Lådor

- **modellens fel**: faktumet står i anteckningarna eller i fönstret, men svaret blev fel.
- **faktumet borta — ämnet nämns**: anteckningarna nämner samma sak som frågan gäller, men
  den efterfrågade detaljen är struken.
- **faktumet borta — ämnet saknas**: anteckningarna nämner inte det frågan gäller. Med
  tillägget **närliggande** när samma samtal eller ett grannämne finns kvar, men inte saken
  själv.
- **nollställda**: anteckningarna täcker bara samtalen i fönstret och högst ett par till.
  Bedömt på innehållet, inte på en token-gräns: de elva har 62–733 tokens, och det finns ingen
  tydlig lucka i token-siffrorna som i KU.
- Tillägg: **E** (datat är otydligt).

Gränsen mellan "ämnet nämns" och "ämnet saknas — närliggande" är en bedömning. Den säkra
siffran är summan: faktumet står inte i anteckningarna i 45 av 47 fel.

## Rader

```
ad7109d1 SSU: faktumet borta — ämnet saknas
36580ce8 SSU: nollställda — anteckningar 62 tokens, på kinesiska, bara sista samtalet
86f00804 SSU: faktumet borta — ämnet saknas; närliggande: "a Saturday spent reading", boken nämns inte
c14c00dd SSU: faktumet borta — ämnet saknas; anteckningarna är på italienska
95bcc1c8 SSU: nollställda — anteckningar 361 tokens
66f24dbb SSU: faktumet borta — ämnet saknas
94f70d80 SSU: faktumet borta — ämnet saknas; närliggande: samtalet finns kvar ("coffee tables … IKEA"), bokhyllan nämns inte
ccb36322 SSU: faktumet borta — ämnet saknas
c5e8278d SSU: nollställda — anteckningar 393 tokens
726462e0 SSU: faktumet borta — ämnet saknas
caf9ead2 SSU: faktumet borta — ämnet saknas
7527f7e2 SSU: faktumet borta — ämnet saknas
5d3d2817 SSU: faktumet borta — ämnet saknas
3f1e9474 SSU: faktumet borta — ämnet saknas; närliggande: "conversation with an old friend", varken Sarah eller destiny nämns
faba32e5 SSU: faktumet borta — ämnet nämns ("Alex's marinated ribs"), 24 timmar borta
60d45044 SSU: faktumet borta — ämnet saknas
8a137a7f SSU: faktumet borta — ämnet saknas
c960da58 SSU: faktumet borta — ämnet saknas
c19f7a0b SSU: faktumet borta — ämnet saknas
b86304ba SSU: modellens fel, E — "flea market find … worth triple" står både i anteckningarna och i fönstret; frågan säger "painting of a sunset", evidensen säger "flea market find" (som i M2)
75499fd8 SSU: faktumet borta — ämnet saknas
15745da0 SSU: faktumet borta — ämnet nämns ("vintage cameras"), tre månader borta
311778f1 SSU: nollställda — anteckningar 575 tokens
e01b8e2f SSU: faktumet borta — ämnet saknas
f8c5f88b SSU: nollställda — anteckningar 468 tokens
21436231 SSU: faktumet borta — ämnet saknas
37d43f65 SSU: faktumet borta — ämnet nämns ("upgraded their laptop's RAM"), 16GB borta
76d63226 SSU: faktumet borta — ämnet nämns ("new smart TV"), storleken borta
8550ddae SSU: faktumet borta — ämnet saknas; närliggande: "signature cocktails", lavender gin fizz nämns inte
bc8a6e93 SSU: faktumet borta — ämnet saknas; närliggande: "lemon desserts", tårtan och kalaset nämns inte
dccbc061 SSU: faktumet borta — ämnet saknas
1faac195 SSU: faktumet borta — ämnet saknas (en "friend Emily" nämns, inte systern)
29f2956b SSU: nollställda — anteckningar 352 tokens
a06e4cfe SSU: faktumet borta — ämnet saknas
b320f3f8 SSU: nollställda — anteckningar 733 tokens, till största delen en CV-mall från ett utfyllnadssamtal
4100d0a0 SSU: modellens fel — "my mixed ethnicity - Irish and Italian" står i fönstret
118b2229 SSU: nollställda — anteckningar 318 tokens
853b0a1d SSU: nollställda — anteckningar 401 tokens
6f9b354f SSU: faktumet borta — ämnet saknas
d52b4f67 SSU: nollställda — anteckningar 468 tokens
8e9d538c SSU: faktumet borta — ämnet nämns ("worsted weight yarn stash"), antalet borta
0862e8bf SSU: nollställda — anteckningar 268 tokens
3d86fd0a SSU: faktumet borta — ämnet saknas
af8d2e46 SSU: faktumet borta — ämnet nämns ("tend to overpack … Costa Rica"), antalet borta
4fd1909e SSU: faktumet borta — ämnet saknas
3b6f954b SSU: faktumet borta — ämnet saknas
a82c026e SSU: faktumet borta — ämnet saknas
```

## Fördelning

| låda | antal |
|---|---:|
| faktumet borta — ämnet saknas | 28 |
| varav närliggande | 5 |
| faktumet borta — ämnet nämns | 6 |
| nollställda | 11 |
| modellens fel | 2 |
| summa | 47 |

45 av de 47 svaren är "I do not know". `4100d0a0` svarar "I do not know your ethnicity …" och
`b86304ba` "I do not know", båda med faktumet i fönstret.

I M2 var 8 av `RetrievalMemory`s 9 SSU-fel med evidensen i kontexten modellens "I do not know".
Här är den lådan nästan tom: 2 av 47.

---

# Rätta svar (34)

## Lådor

- **anteckningarna**: svaret står i anteckningarna, evidensen ligger inte i fönstret.
- **fönstret**: evidensen ligger i fönstret, svaret står inte i anteckningarna.
- **båda**: svaret står på båda ställena.
- **gissning**: svaret står varken i anteckningarna eller i fönstret.

För KU står också vad anteckningarna hade av gamla och nya värdet.

## Rader

```
c8c3f81d SSU: anteckningarna
51a45a95 SSU: anteckningarna, E — "Target" står inte i evidensmeningen (som i M2); svaret sattes ihop av anteckningarnas "Cartwheel app from Target" och kupongen
6b168ec8 SSU: anteckningarna
8ebdbe50 SSU: anteckningarna
545bd2b5 SSU: anteckningarna
6ade9755 SSU: fönstret — anteckningarna har yoga och Down Dog, inte Serenity Yoga; svaret är försiktigt ("have a connection to Serenity Yoga") men godkändes
e47becba SSU: båda
577d4d32 SSU: anteckningarna
f4f1d8a4 SSU: fönstret — anteckningarna (på italienska) säger att mixern var en födelsedagspresent, inte från vem
58ef2f1c SSU: fönstret — anteckningarna slutar mitt i meningen ("They enjoyed volunteering at the "), precis där uppgiften skulle stå
25e5aa4f SSU: anteckningarna
19b5f2b3 SSU: anteckningarna
ec81a493 SSU: anteckningarna
86b68151 SSU: anteckningarna
b6019101 KU: båda — bara nya värdet i anteckningarna
0f05491a KU: båda — bara nya värdet i anteckningarna
6aeb4375 KU: fönstret — inget av värdena i anteckningarna
7e974930 KU: fönstret — inget av värdena i anteckningarna (246 tokens, nollställda)
ed4ddc30 KU: anteckningarna — bara nya värdet
0e4e4c46 KU: fönstret — inget av värdena i anteckningarna
603deb26 KU: anteckningarna — bara nya värdet; evidenssessionens senare turer ligger i fönstret, och enligt M2-läsningen upprepar tur :10 faktumet
59524333 KU: anteckningarna — bara nya värdet
7a87bd0c KU: anteckningarna — bara nya värdet
72e3ee87 KU: anteckningarna — bara nya värdet
d7c942c3 KU: anteckningarna — bara nya läget; svaret är en slutsats ("It seems likely") men godkändes
852ce960 KU: fönstret — inget av värdena i anteckningarna
2698e78f KU: anteckningarna — bara nya värdet
1cea1afa KU: anteckningarna — bara nya värdet; anteckningarna slutar mitt i meningen ("User recently finished reading ")
2133c1b5 KU: båda — bara nya värdet i anteckningarna
ba61f0b9 KU: anteckningarna — bara nya värdet
4d6b87c8 KU: anteckningarna — bara nya värdet
4b24c848 KU: anteckningarna — bara nya värdet
8fb83627 KU: båda — bara nya värdet i anteckningarna
50635ada KU: gissning, frågar efter gamla — anteckningarna har bara nya statusen (Premier Gold); Premier Silver står varken där eller i fönstret
```

## Fördelning

| låda | SSU | KU | summa |
|---|---:|---:|---:|
| anteckningarna | 10 | 11 | 21 |
| fönstret | 3 | 4 | 7 |
| båda | 1 | 4 | 5 |
| gissning | 0 | 1 | 1 |
| summa | 14 | 20 | 34 |

---

# Felen, båda typerna

| | KU | SSU | summa |
|---|---:|---:|---:|
| fel | 41 | 47 | 88 |
| nollställda | 6 | 11 | 17 |
| värdet står inte i anteckningarna (alla lådor utom "nästan rätt", "frågar efter gamla, gamla borta" och "modellens fel") | 37 | 45 | 82 |

# Alla 122: vad stod i anteckningarna?

**KU (61 frågor): vad anteckningarna hade om det frågan gäller**

| | antal |
|---|---:|
| bara nya värdet | 19 |
| bara gamla värdet | 0 |
| båda värdena | 0 |
| inget av värdena | 42 |

De 19: 15 rätta (lådorna "anteckningarna" och "båda"), `50635ada`, `07741c45`, `0977f2af` och
`e66b632c`. Det går inte alltid att skilja "det nya skrev över det gamla" från "det gamla var
redan glömt": evidenssessionerna ligger ofta veckor isär. I `4d6b87c8` (två dagar isär) och
`1cea1afa` (en dag isär) måste det gamla värdet ha stått i anteckningarna när det nya kom.

**SSU (61 frågor)**

| | antal |
|---|---:|
| faktumet står i anteckningarna | 12 |
| faktumet står inte i anteckningarna | 49 |

De 12: 11 rätta och `b86304ba`.

**Båda typerna**

- Det efterfrågade värdet stod i anteckningarna i 28 av 122 frågor. Svaret blev rätt i 26 av
  de 28. De två andra är `07741c45` (underkänt, E) och `b86304ba` (E).
- I 3 frågor gällde frågan det gamla värdet medan anteckningarna bara hade det nya:
  `0977f2af` och `e66b632c` (fel), `50635ada` (rätt genom gissning).
- Evidensen låg i fönstret i 16 frågor, 12 av dem rätt.
- Anteckningarna ensamma gav 21 rätta svar (10 SSU, 11 KU), mot baslinjens 3 och 9.

# Att kontrollera mot raderna

- Gränsen för "nollställda" i KU: stämmer det att de sex har 165–511 tokens och alla andra
  KU-fel minst 808?
- "Nollställda" i SSU är bedömt på innehållet. Går det att kontrollera, till exempel genom att
  se hur många samtal slutanteckningarna faktiskt täcker?
- Vad gjorde anteckningarna korta i de 17: ett kort svar från modellen (första eller andra
  anropet) eller klippet? Syns det i raderna?
- Mellanstegen: finns anteckningarna efter varje samtal sparade, så att det går att se när
  ett värde försvann och om det var klippet som tog det?
- `07741c45`: domarens skäl för "no".
- `4100d0a0`: evidensen stod i fönstret och svaret blev ändå "I do not know your ethnicity".
  Är det samma sorts miss som i M2, eller en vägran att uttala sig om etnicitet?
- Anteckningar på annat språk: italienska i `89941a94`, `c14c00dd` och `f4f1d8a4`, kinesiska i
  `36580ce8`. Det är 4 av 122 enligt läsningen.
  Prompten i 0015 säger "Keep the notes in the language of the conversation". Hur många av de
  122 har anteckningar som inte är på engelska?
- I `5a4f22c0` och `830ce83f` gäller frågan en annan person (Rachel). Prompten i 0015 säger
  "keep what is about the user … drop detail about anything else first". Finns det fler fel
  där svaret gäller någon annan än användaren? Motexempel: i `ba61f0b9` (rätt) står Rachels
  team kvar i anteckningarna.
- Flera evidensmeningar är inskott ("by the way …") i ett samtal om något annat. I
  `94f70d80`, `bc8a6e93` och `830ce83f` finns samtalets huvudämne kvar i anteckningarna medan
  inskottet är struket. Hur stor andel av evidensturerna är sådana inskott?
- Anteckningarna innehåller mycket från utfyllnadssamtalen (spökhistorien i `45dc21b6`,
  CV-mallen i `b320f3f8`). Hur stor del av de 1 000 tokens går till sådant?
- **Anteckningar som slutar mitt i en mening.** `58ef2f1c` slutar "They enjoyed volunteering
  at the " och `1cea1afa` slutar "User recently finished reading ". Båda slutar precis där en
  titel inom citattecken skulle börja. Hypotes: ett citattecken som inte är escapat stänger
  JSON-strängen, och resten av anteckningarna går förlorad. Loopen i 0016 börjar på samma
  sätt (`"Isis Unveiled" , "Isis Unveiled" : …`). Kontrollera i råsvaren: hade svaret fler
  nycklar än `summary`, eller är det harnessens tolkning som klipper? Hur många av de 5 874
  sammanfattningarna slutar utan skiljetecken? Det som går förlorat är slutet, alltså det
  nyaste, och det räknas varken som klipp eller hopp.
- **`36580ce8` (62 tokens, kinesiska).** Anteckningarna börjar "4和ME2.5", alltså mitt i
  "ME2.4". Klippet i 0017 letar meningsstart efter `.`, `!`, `?` eller radbrytning. Kinesisk
  text använder "。", så de enda punkterna är de i "ME2.4", "ME2.5" och så vidare, och klippet
  behöll bara det som följde efter en av dem. Stämmer det, och förklarar samma sak någon annan
  av de nollställda?
- **Nollställda bland de rätta.** `7e974930` har 246 tokens. `6ade9755`, `6aeb4375`,
  `19b5f2b3` och `ba61f0b9` har 630–670 tokens och täcker också bara de sista samtalen. Hur
  många av de 122 är nollställda, räknat på samma sätt för alla?
- **Domarens gräns.** `6ade9755` ("have a connection to Serenity Yoga") och `d7c942c3` ("It
  seems likely") godkändes, `07741c45` ("planning to store … in a shoe rack") underkändes.
- **Avstånd.** Hur beror andelen rätt på avståndet mellan evidensen och frågan? De rätta
  svaren ur anteckningarna har evidensen 9 000–33 000 tokens före frågan.
- `603deb26`: ligger tur :10, som upprepar faktumet, i fönstret?
