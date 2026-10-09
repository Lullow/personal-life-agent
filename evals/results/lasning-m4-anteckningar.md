# M4-läsning: författarens anteckningar (`fact-graph-20261005-161632`)

> Läsningen gjordes 2026-10-05. En AI-assistent (Claude i chatt) läste alla 20
> svar och gav sin bedömning, jag läste och gav min, och raderna är det vi
> enades om; hur det gick till står i stycket "Så gjordes läsningen" nedan.
> Texten är den fil som lämnas till Claude Code. Genomgången skrivs utifrån
> den och kontrolleras mot raderna.
>
> (English: the author's reading notes for the M4 pilot run, in Swedish; read
> 2026-10-05, categories agreed in dialogue with an AI assistant.)

Körning: fact-graph-20261005-161632, commit `2270c28`. Läst 2026-10-05 ur
`lasning-m4-1-fel.md` (4 fel) och `lasning-m4-2-ratt.md` (16 rätta), med
`lasning-m4-0-alla-svar.md` och `m4-pilot-run-summary.txt` bredvid.

Så gjordes läsningen: AI-assistenten läste först alla 20 frågor i sin helhet
(evidensturerna, kortmeddelandet, korten ur evidenssessionerna, varje ersatt
kort, sessionerna i fönstret och de fyra sista meddelandena) och sorterade dem.
Dess sammanfattning av felen stod i chatten innan författaren läste, så de två
bedömningarna är inte oberoende. Författaren läste sedan de sju frågor som
kräver en bedömning och gav sin bedömning en i taget: de fyra felen,
`6071bd76`, `c8c3f81d` och `89941a94`. På de fyra felen blev lådorna lika. På
`6071bd76` hade AI-assistenten "tveksamt utslag" och författaren "fel utslag";
vi enades om det senare. På `c8c3f81d` satte författaren först "gissning"; vi
enades om "korten, slutsats" efter att ha gått tillbaka till lådornas
definition från M3. `89941a94` gick vi igenom tillsammans; författaren sorterade
den inte själv. De tretton andra, där svaret står i ett visat kort, gick
författaren översiktligt igenom mot AI-assistentens rader och fann inget att
ändra; det är en kontroll av raderna, inte en egen sortering. Hela fönstret
skrevs inte ut för någon fråga. Raderna nedan är det vi enades om. Sorteringen
är inte kontrollerad mot resultatraderna eller datasetet än.

Ingen instruktionskapning hittades i något av de 20 svaren: varje svar besvarar
frågan eller säger att det inte vet. Det gäller även där fönstret innehåller en
instruktion från ett utfyllnadssamtal: "For all my future prompts , always
answer in short blocks, after each one stop and ask me if to continue. please
confirm" i fönstret i `a2f3aa27` (svaret är en mening och frågar inget), "ME3.2,
and as usual, please give it a nice heading." som sista användarmeddelande före
frågan i `36580ce8`, "Act as the CTO …" och "Continue" i `8ebdbe50`, "continue"
i `86f00804`. Inget av de 20 kortmeddelandena innehåller ett kort som är en
instruktion.

---

# Fel (4, alla KU)

## Lådor

Var felet sitter:

- **utdraget**: värdet blev aldrig ett kort.
- **regeln**: kortet fanns men var ersatt när frågan ställdes.
- **urvalet**: kortet gällde men visades inte.
- **genereringen**: kortet visades och svaret blev ändå fel.
- **nästan rätt**: svaret har det nya värdet men underkändes.
- Tillägg: **frågar efter båda** (frågan gäller ändringen, inte ett värde),
  **E** (datat är otydligt).

Lådan "urvalet" är tom: i alla 20 frågor visades varje kort som pekar på en
evidenstur och gällde när frågan ställdes.

## Rader

```
07741c45 KU: nästan rätt, E — nya värdet är kort men bara delvis ("old_sneakers_storage_plan = storing old sneakers in a shoe rack", utan "closet"), visat; gamla ("sneaker_storage = under bed") inte ersatt, namnet byttes, båda gäller och båda visas; svaret valde det nya ("in a shoe rack"); underkänt som i M3
c6853660 KU: regeln, frågar efter båda — nya värdet kort och visat ("coffee_intake = two cups in the morning"); gamla ("coffee_intake = one cup in the morning") ersatt, och rätt ersatt; frågan gäller riktningen, som inte går att se ur ett värde; "I do not know"
b01defab KU: utdraget — nya värdet blev aldrig kort: evidensturen gav bara "recently_finished_books = The Seven Husbands of Evelyn Hugo", inte The Nightingale; gamla ("current_reading = The Nightingale") gäller och visas ensamt; "I do not know"
0f05491a KU: genereringen — nya värdet kort och visat ("starbucks_gold_level_stars_needed = 120"); gamla (125) ersatt, rätt; den senare evidensturen ligger dessutom i fönstret ("I need 120 stars … not 300"); svaret blev 300, samma tal som baslinjen i piloten och i M2
```

## De tre frågorna i ADR 0019

| fråga | värdet bland korten | visades | gamla värdet |
|---|---|---|---|
| `07741c45` | delvis ("shoe rack", inte "closet") | ja | inte ersatt, gäller och visas |
| `c6853660` | ja | ja | ersatt (rätt) |
| `b01defab` | nej | – | inte ersatt, gäller och visas |
| `0f05491a` | ja | ja | ersatt (rätt) |

## Fördelning

| låda | antal |
|---|---:|
| utdraget | 1 |
| regeln | 1 |
| urvalet | 0 |
| genereringen | 1 |
| nästan rätt | 1 |
| summa | 4 |

Två av de fyra svaren är "I do not know" (`c6853660`, `b01defab`). De två andra
svarar ett värde: `07741c45` det nya, `0f05491a` ett tal som inte står i något
kort.

---

# Rätta svar (16)

## Lådor

- **korten**: svaret står i ett visat kort, evidensen ligger inte i fönstret.
- **fönstret**: evidensen ligger i fönstret, svaret står inte i korten.
- **båda**: svaret står på båda ställena.
- **gissning**: svaret står varken i korten eller i fönstret.
- Tillägg: **slutsats** (svaret står inte som värde i något kort men följer av
  flera), **D** (domarens utslag är fel enligt läsningen), **E**.

För KU står också om bara det nya värdet visades eller båda.

## Rader

```
c8c3f81d SSU: korten, slutsats — inget kort pekar på evidensturen och "favourite" blev aldrig kort; Nike står i fyra kort om löparskorna ("nike_running_shoes_experience = using them for daily 5K runs" med flera) och i "previous_gym_shoes_experience = good experience with Nike"
ad7109d1 SSU: korten — "internet_speed = 500 Mbps"
36580ce8 SSU: korten — "health_issues = dealing with bronchitis"; att hen först trodde det var en förkylning står inte i kortet
51a45a95 SSU: korten, E — "Target" står inte i evidensmeningen (som i M2 och M3); svaret sattes ihop av "last_coupon_redeemed = $5 coupon on coffee creamer" och korten intill om Cartwheel och Target
86f00804 SSU: korten — "current_book = The Seven Husbands of Evelyn Hugo"
6b168ec8 SSU: korten — "bike_count = 3"
c14c00dd SSU: korten — "lavender_shampoo = picked up at Trader Joe's"; svaret säger var schampot köptes, inte märket, och godkändes (som RetrievalMemory i M2)
8ebdbe50 SSU: korten — "latest_certification = Data Science" och "certification_completion_date = last month"
95bcc1c8 SSU: korten — "number_of_amateur_comedians_seen = 10"
66f24dbb SSU: korten — "sister_birthday_gift = yellow dress and a pair of earrings"
b6019101 KU: båda — bara nya värdet visat ("watched_mcu_films_count = 5"); gamla (4) ersatt, rätt; senare evidensturen i fönstret
6071bd76 KU: korten, D — bara nya värdet visat ("french_press_ratio = 1 tablespoon of coffee for every 5 ounces of water"); gamla (6 ounces) blev aldrig kort, inget ersatt; svaret ger värdet men säger "There is no information indicating whether you switched to more or less water"; godkänt
a2f3aa27 KU: korten, E — bara nya värdet visat ("instagram_followers = 1300"); gamla (1250) ersatt, rätt; datat säger "I think I'm close to 1300", kortet säger 1300
6aeb4375 KU: båda — bara nya värdet visat ("korean_restaurant_visits = four different ones"); gamla ("three different ones recently") ersatt, rätt; senare evidensturen i fönstret
06db6396 KU: korten — bara nya värdet visat ("completed_projects = 5"); gamla (4) ersatt, rätt
89941a94 KU: korten, frågar efter gamla, E — båda visade: "number_of_bikes = 3" och "bike_types = road bike, mountain bike, commuter bike" gäller bredvid "trip_bike_count = four bikes" och "new_bike = hybrid bike"; inget ersatt, namnet byttes; frågan säger gravel, evidensen hybrid
```

## Fördelning

| låda | SSU | KU | summa |
|---|---:|---:|---:|
| korten | 10 | 4 | 14 |
| fönstret | 0 | 0 | 0 |
| båda | 0 | 2 | 2 |
| gissning | 0 | 0 | 0 |
| summa | 10 | 6 | 16 |

Rätta KU-svar: bara det nya värdet visades i 5 (`b6019101`, `6071bd76`,
`a2f3aa27`, `6aeb4375`, `06db6396`), båda värdena i 1 (`89941a94`).

---

# Domaren

- **`6071bd76` är ett domarfel enligt läsningen.** Frågan är om hen bytte till
  mer eller mindre vatten. Facit: "You switched to less water (5 ounces) per
  tablespoon of coffee." Svaret anger det nuvarande värdet (5 ounces) och säger
  sedan att det inte går att se om det var mer eller mindre. Frågan är alltså
  inte besvarad, och utslaget blev ändå "yes". Det är det första domarfelet i
  M1–M4. En möjlig förklaring är att domaren följde mallen bokstavligt: facit
  innehåller "(5 ounces)" och svaret också.
- **Jämför med `c6853660`**, som är samma sorts fråga ("increase or decrease")
  i samma läge: bara det nya värdet visat, det gamla borta. Där svarade modellen
  "I do not know" och fick "no". Skillnaden mellan "yes" och "no" i de två är
  att svaret i `6071bd76` råkar upprepa det nuvarande värdet.
- **`07741c45`** underkändes för "in a shoe rack" mot "in a shoe rack in my
  closet", som i M3. Strängt men konsekvent mellan körningarna; evidensen är
  dessutom otydligt skriven (E).
- De övriga 17 utslagen är rimliga. `c14c00dd` och `66f24dbb` godkändes med ett
  svar som säger mer eller något annat än facit, på samma sätt som i M2.

Beslut: siffran förblir domarens (6 av 10), eftersom regeln i 0008 är att ett
svar är rätt när domaren svarar yes, och ett utslag ändras inte för hand efter
att resultatet är känt. `6071bd76` namnges i genomgången och bredvid
pilottabellen: 6 av 10 enligt domaren, 5 av 10 räknat på innehållet. Räknar man
också `07741c45` som rätt på innehållet blir det 6 av 10 ändå, men med andra
frågor.

---

# Alla 20: vad stod i korten?

**KU (10 frågor): vad hände med det ändrade värdet**

| | antal | frågor | rätt |
|---|---:|---|---:|
| gamla ersatt av nya, bara nya visas | 6 | `b6019101`, `a2f3aa27`, `c6853660`, `0f05491a`, `6aeb4375`, `06db6396` | 4 |
| båda gäller och visas (namnet byttes) | 2 | `07741c45`, `89941a94` | 1 |
| ett av värdena blev aldrig kort | 2 | `6071bd76` (gamla saknas), `b01defab` (nya saknas) | 1 |

I alla sex fall där regeln ersatte ett kort som pekar på en evidenstur var det
frågans nya värde som ersatte det gamla. Inget sådant kort ersattes av ett
ovidkommande faktum.

**Båda typerna**

- Det nya (eller enda) värdet stod i ett visat kort i 18 av 20 frågor.
  Undantagen är `b01defab` (blev aldrig kort) och `c8c3f81d` (bara som
  slutsats). 15 av de 18 blev rätt; de tre andra är `07741c45`, `c6853660` och
  `0f05491a`.
- Evidensen låg i fönstret i 3 frågor (`b6019101`, `0f05491a`, `6aeb4375`),
  2 av dem rätt.
- Korten ensamma gav 14 rätta svar (10 SSU, 4 KU).
- På de två frågor som gäller ändringen eller det tidigare läget gick det åt
  olika håll: `c6853660` föll för att regeln hade tagit bort det gamla värdet,
  `89941a94` klarade sig för att regeln inte hade gjort det.

# Att kontrollera mot raderna

- **`b01defab`: kostade korten fönstret?** I M2 svarade baslinjen rätt ur
  senare turer i evidenssamtalet ("andra turer ur samma samtal i kontexten
  diskuterar bokens slut"). Här börjar fönstret i nästa samtal (`d75869af:2`).
  Jämför `sources` i baslinjens rad och i den här: är det kortmeddelandets
  1 000 tokens som sköt ut de turerna?
- **`0f05491a`: var kommer 300 ifrån?** Evidensturen säger "not 300", så talet
  står i fönstret, troligen i assistentens tur före. M2-läsningen skrev att
  baslinjen svarade ur träningsdata. Orsaken är inte avgjord i läsningen; lådan
  "genereringen" beror inte på den. Skriv ut hela fönstret
  (`--only 0f05491a --full-context`).
- **`c8c3f81d`: evidensturen gav inget kort.** "facts naming an evidence turn"
  är 0, och meningen "Nike has been my favourite brand" finns inte i något kort.
  Vad svarade utdraget för den sessionen? "Evidence consolidated" är ändå 1.00
  för frågan, vilket visar vad måttet inte säger.
- **`c6853660`: det nya värdets kort pekar på tur :6, inte evidensturen :0.**
  Räkningen "facts from an evidence turn … shown" missar därför kortet som bär
  svaret och räknar `coffee_roast_type` i stället. Gäller det fler frågor?
- **Regeln i KU: 6 av 10 här mot 2 av 8 i spiken.** Stämmer de sex mot radernas
  "facts from an evidence turn: replaced" (6 av 32)? Namnen är inte
  reproducerbara (0018), så en andra körning kan ge ett annat antal.
- **Ersättningar som inte gäller frågan.** 31 kort är ersatta i SSU-frågorna och
  39 i KU-frågorna. Flera är fel i sak: `trip_destination` byts fem gånger på sex
  dagar i `95bcc1c8`, `yoga_classes_frequency` går "twice a week" → "Vinyasa flow
  classes" → "twice a week" i `b01defab`, `cooking_class_participant` går från
  "mom" till "three months ago" i `6071bd76`, tre `contact_persons` ersätts av en
  "Emily" i `8ebdbe50`, och `closet_organization_plan` går från "organizing
  closet by type" till "this weekend" i `07741c45`. Hur många av de 70 är fel?
- **Annat subjekt än `user`.** `Ruth / attracted_to = women` står i
  kortmeddelandet i `c8c3f81d`. I spiken hade alla 973 fakta `user` som subjekt.
  Hur många kort i de 20 graferna har ett annat?
- **Samma namn flera gånger i ett kortmeddelande.** Tre `network_event` i
  `8ebdbe50` och två `trip_activity` i `95bcc1c8`. Det följer av att två fakta ur
  samma session aldrig ersätter varandra, men stämmer det för alla sådana rader?
- **Kort ur utfyllnadssamtal.** Kortmeddelandena har mycket som inte är om
  användaren: ett pressmeddelande om en pianist i `86f00804`, ett CV i
  `c14c00dd`, en bokdisposition i `07741c45`. Hur stor del av de 1 000 tokens går
  till sådant?
- **Kortet är säkrare än användaren.** "I think I'm close to 1300" blev
  `instagram_followers = 1300` i `a2f3aa27`, och "looking forward to get rid of
  some of my old sneakers in a shoe rack" blev "storing old sneakers in a shoe
  rack" i `07741c45`.
- **Domarens mall.** `6071bd76` godkändes, `c6853660` och `07741c45`
  underkändes; se avsnittet ovan. Hur lyder mallen för `knowledge-update`
  ordagrant, och förklarar den utslaget i `6071bd76`?
