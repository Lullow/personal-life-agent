# Labbjournal — minnesprojektet

Senaste överst. Vad jag gjorde, vad jag fick, vad som förvånade mig.

## 2026-10-03

Jag läste själv de 27 fall som avgör hypoteserna, uppdelade i fyra
läsfiler, och skummade alla 244 svar. Inget svar följde en instruktion
från en utfyllnadssession, och jag hittade inga domarfel. Sedan jämförde
jag min bedömning med agentens preliminära sortering. Vi skilde oss på
tre frågor, och där höll min: 6071bd76 och f685340e är felslut, inte det
gamla värdet, och c4ea545c är "hittade inte det nya".

Det läsningen gav: av sökningens 13 KU-fel med båda värdena i kontexten
svarade 6 med det gamla värdet, 5 hittade inte det nya och 2 var felslut.
Av de 9 SSU-fel där evidensen var framme svarade 8 "I do not know" trots
att svaret stod ordagrant i kontexten. Det nionde är ett datafel
(51a45a95, Target-turen var inte med). Baslinjens 2 rätta svar utan
evidens var inga gissningar, de kom från omarkerade turer som upprepar
faktumet. Två par av KU-frågor delar evidens (07741c44/45 och
89941a93/94).

Hypoteserna: H1 håller. H2 håller i första halvan, sökningen hittar gamla
fakta (50 mot 3 rätt på SSU). Andra halvan är inte tydlig: 47 rätt på KU
mot 50 på SSU är tre frågor, och det är inom slumpen. Mekanismen finns
ändå. I 6 av 61 frågor svarade modellen med det gamla värdet fast båda
fanns framme. Med båda värdena i kontexten blev 45 av 58 rätt.

Det viktigaste jag tar med mig: 23 av sökningens 25 fel hade evidensen i
kontexten. Felen är modellens, inte minnets.

Resultattabellen finns nu i docs/results.md, med tabell, KU-uppdelning,
analys och begränsningar. evals/results_table.py räknar fram varje siffra
ur raderna, och --check hittar alla 17 siffror i texten. Kostnaden
skiljer inte raderna åt: sökningen ligger ungefär 24 tokens högre per
anrop.

Kvar i M2 är metodavsnittet, avstämningen av M2 och att läsa av fakturan
hos OpenRouter. Måndag 5 oktober bestämmer jag om M3 ryms före stoppet
tisdag 6 oktober.

Commits: da8cddd (läsningen), be8cb10 (tabellen).

## 2026-10-02

Började med en avstämning. M1 skulle ha varit klar 29 september, och
inget hade hänt sedan 27:e. Riggen, piloten och ADR 0004–0010 var klara,
men metodutkastet var en enda mening. Jag stängde M1 tre dagar sent och
flyttade metodavsnittet in i M2.

Sedan ADR 0011: BM25 i stället för embeddings, som ADR 0010 hade antagit.
Jag valde BM25 eftersom det inte gör några modellanrop. Torrkörningen kan
räkna recall gratis, siffrorna går att upprepa utan nyckel, och jag
slipper nya regler för tokenräkning, cache och långa meddelanden. Priset
är att matchningen är lexikal, så raden heter BM25-sökning i rapporten
och inte sökning i allmänhet.

Tre regler låstes före mätningen: varje tur rangordnas för sig, även
assistentens; budgeten fylls i rangordning och turer som inte ryms
hoppas över; turerna visas i den ordning de sades. Den sista är den
viktiga. Modellen ser inga datum, så ordningen är det enda som säger
vilket värde som är nyast. Med bästa träff först hade H2 blivit sann per
konstruktion.

Innan commit gick jag igenom fallgroparna. Assistentens turer står för
87 % av alla tokens men bara 2 av 185 evidensturer, så jag deklarerade en
sidosiffra i förväg: recall med bara användarens turer. Riggens
kostnadsräkning missar 4 tokens per meddelande, och sökningen skickar
fler korta meddelanden än baslinjen, så kostnaden redovisas med påslag.
Ingen evidenstur är större än budgeten. Siffrorna går att räkna om med
evals/verify_adr_0011.py.

Därefter byggde jag RetrievalMemory i memory.py, 315 tester gröna.
Kontrakttesterna behövde frågor som delar ett ord med den post de väntar
sig, eftersom en strategi som söker på relevans inte returnerar något
för "q".

Torrkörningen på alla 122 frågor: sökningen når evidensen i 59 av 61 SSU
och 61 av 61 KU, baslinjen i 6 och 11. Farhågorna slog inte in. Recall
med bara användarens turer blev nästan samma, och sökningen skickar
43–45 meddelanden per anrop, inte 200.

---

Riktig körning, efter att saldot var påfyllt. Först ett röktest med en
fråga per typ: leverantören räknade 8 240 tokens mot riggens 8 077,
alltså exakt 4 per meddelande plus 3. Nike-frågan fick "I do not know" i
röktestet och "Nike" när den kördes om på samma kontext. Modellen är
alltså inte deterministisk ens vid temperatur 0.

Båda strategierna kördes sedan på 122 frågor utan fel. Sökningen fick 50
av 61 rätt på SSU och 47 av 61 på KU, baslinjen 3 och 9. Riggen räknar
5,01 dollar; fakturan är inte avläst än.

Dessutom finns en karta över projektet som artefakt, som ska uppdateras
efter varje milstolpe, och dokumenten ligger som kunskap i ett projekt i
Claude Desktop. De laddades upp för hand eftersom GitHub-väljaren bara
visar main.

Commits: cd04afa (M1 stängd), cb12f5c (ADR 0011), c242d35 (bygget),
f46b438 (körningen).

## 2026-09-27

Planen för M1 var först att göra två–tre ADR:er, men det blev sex.
Anledningen var att LongMemEval-datan hade flera konstigheter som annars
lätt hade kunnat påverka mätningen utan att man märker det,
till exempel sessioner i fel ordning, sessioner efter frågan och dubblerade sessioner.

En sak som överraskade mig var att klockordningen inom en dag gav min baslinje
lägre räckvidd än listordningen: beviset nås i 14 mot 21 av 69 KU-frågor,
räknat utan modellanrop. Jag valde ändå klockordningen eftersom den var mer
neutral och bättre motiverad.

Jag upptäckte också att vårt KU-mått byggde på antagandet att frågan alltid handlar om det senaste värdet.
Men vissa frågor handlar i stället om ett tidigare värde.
Det gav en bättre hypotes: en metod som skriver över gammal information borde bli bättre på frågor om nuläget,
men sämre på frågor om tidigare värden. Därför märker jag upp de frågorna innan jag tittar på resultaten.

En annan viktig sak var att LongMemEval inte klipper historiken alls, men att
datan aldrig har sessioner efter frågans dag, bara upp till 15 timmar efter
frågan samma dag. Därför ställer vi frågan 23:59 den dagen.

Jag fick också ännu ett exempel på att agenten kunde ge en säker men felaktig varning
eftersom den inte hade läst hela texten.
Därför gjorde jag `verify_adr_numbers.py`, så att viktiga siffror går att kontrollera direkt med kod.

Jag insåg också att ett modellbyte inte betyder att modellen "glömmer projektet" på det sätt jag först tänkte.Varje anrop är redan tillståndslöst. Det jag egentligen riskerar att förlora är hur väl promptarna passar modellen
inte själva arbetet.

Kostnaden hittills är nästan noll; har kostat 0,433 dollar(inkluderar ett kontrollanrop), ungefär fem kronor.
Det dyrare steget blir M3 och konsolideringen.
Jag funderade på lokala modeller på min 3090, men valde bort det eftersom det skulle bli mer komplicerat, 
och rättningen ändå behöver göras med GPT-4o för att resultaten ska vara jämförbara.

Det som fortfarande är öppet är bland annat i vilken ordning RetrievalMemory ska ge historiken till modellen (M2),
om svarsprompten i 0008 håller när den testas, vilken modell som ska användas för konsolideringen i M3 
och vilket statistiskt test som passar bäst.

---

Piloten kördes efter lunch och jag gick igenom alla 20 frågor. Baslinjen hittade rätt evidens i 3 av 20 fall, 
och de 17 missarna svarade alla "I do not know". H1 håller, men det är mest en kontroll av att riggen fungerar
och ger en tydlig ribba inför M2.

Den enda frågan som blev fel trots att evidensen fanns i kontexten var Starbucks-frågan. Där följde modellen
sin egen kunskap i stället för användarens uppgift. Det är ett modellfel, inte ett retrievalfel, så rapporten 
behöver visa både andel rätt och hur ofta rätt evidens faktiskt nådde kontexten.

Jag läste också KU-frågorna fel först och trodde att fyra facit var fel. Det visade sig att jag bara hade tittat
på den äldre av två evidensturer. Det behöver förklaras tydligt i metoddelen.

Piloten kostade 0,4135 dollar. Kvar nu är att bestämma antal frågor per typ, 
kontrollera kostnaden mot OpenRouter och fylla på saldo inför M2.

---

Piloten kostade 0,4135 dollar, och min egen kostnadsräkning stämde mot OpenRouter på en tiondels cent. 
Det känns bra, för då vet jag att tokenräkningen faktiskt håller.

Utifrån det räknade jag på hela projektet. Själva svaren och rättningen är billiga, ungefär 70 kr för alla 
tre strategierna. Det dyra är M3, där konsolideringen måste läsa hela historiken för varje fråga. 
Det är i snitt 48 sessioner gånger 122 frågor. Med gpt-4o hade bara den delen kostat ungefär 850 kr 
med korta sammanfattningar och över 1200 kr med längre. Det hade ätit upp nästan hela budgeten och 
lämnat väldigt lite utrymme för en omkörning.

Därför valde jag gpt-4o-mini för konsolideringen och N = 61 per frågetyp, alltså alla frågor som klarar urvalet. 
Nackdelen är att ett dåligt resultat i M3 då kan bero på att modellen sammanfattar sämre, 
inte bara på själva metoden. Det skriver jag därför som en begränsning.

Om tiden finns tänker jag kontrollera det genom att köra fem av historikerna med gpt-4o också. 
Det kostar ungefär 30–75 kr extra. Vilka fem som ska användas är bestämt i förväg, 
de första fem KU-frågorna i 0005-ordningen, så att jag inte kan välja ut dem efter att jag sett resultaten.
Det beslutet ligger i ADR 0010.

Jag gjorde också evals/estimate_cost.py --check, som räknar om siffrorna i ADR 0010 direkt från pilotresultaten och datasetet.
Första körningen hittade två fel, men de låg i skriptets sökmönster och inte i själva siffrorna. 
Det följer samma princip som verify_adr_numbers.py: viktiga siffror i texten ska gå att kontrollera med kod.

Det som är kvar i M1 nu är metodutkastet, avstämningen på tisdag och att fylla på OpenRouter inför M2. 
Ungefär 300 kr bör räcka för resten av projektet, inklusive en omkörning.

## 2026-09-26

Jag ändrade beslutet om ordningen flera gånger innan jag landade rätt. 
Varje ändring kom efter att jag hittat något nytt, 
och två gånger upptäckte agenten själv att dess tidigare resonemang var fel.

Det som till slut avgjorde var att det egentligen inte finns någon 
riktig tidsordning mellan ett bevis och en utfyllnadssession. 
Utfyllnaden hör inte direkt till berättelsens tidslinje. 
Därför är det viktigare att ordningen är neutral än att försöka hitta en "korrekt" ordning.

När jag jämförde alternativen såg jag att klockordning låg närmare slumpen, 
medan listordning oftare placerade bevisen sist. 
Det kan bero på hur testhistoriken byggdes och riskerar därför att gynna baslinjen. 
Därför behöll ajg klockordningen som huvudval och använder listordning som en extra känslighetsanalys.

En annan lärdom var att granskningen kan fortsätta hur länge som helst om man inte har en tydlig stoppregel. 
Därför bestämde jag att efter commit är ADR-besluten stängda. 
Nya fynd dokumenteras som begränsningar i rapporten, om de inte visar att själva testet mäter fel.

Det här var också tredje gången på två dagar som agenten uttryckte något väldigt säkert som visade sig vara fel. 
Därför vill jag att siffror som påverkar viktiga beslut alltid ska komma från ett skript som går att köra om och kontrollera.

## 2026-09-25

Gjorde om planen från steg till daterade milstolpar, med ett preliminärt
slutdatum fredag 9 oktober. M1 baslinjen (tis 29/9), M2 två strategier (fre 2/10),
M3 tre strategier (tis 6/10), sedan bara rapport. Varje milstolpe mäter
allt som byggts hittills, så steg 6 "full mätning" försvann som eget steg.

**Anledning**: Tidigare plan var provisorisk och hade inte en bra grund.

Persistens (steg 4) flyttades till efter deadline: mätningen behöver den
inte, bara agenten.

Skrev också ner forskningsfrågan och tre hypoteser för första gången:
baslinjen som golv, RetrievalMemory som svarar fel när ett faktum ändrats,
ConsolidatingMemory som klarar ändrade fakta men tappar detaljer.

Nytt: kapningsordning (steg 4 → antal frågor → ConsolidatingMemory, M2
stannar alltid) och hårt stopp för M3. 

**Anledningen**: deadlinen 9 oktober går inte att flytta, 
så omfånget är det enda som kan ge efter. 
Ville bestämma vad som stryks medan jag har överblick, 
inte när en milstolpe redan dragit över.

## 2026-09-13

Tre städrundor av dokumentationen, varje gång hittades nya missar.
Mönstret: meningar skrivna i nutid om saker som inte finns än.
"Memory persistence writes to its own store" beskriver ett system
som inte existerar — kravet är "must write". Beskrivning och
specifikation ser identiska ut i markdown men gör olika saker för
en agent som läser filen: den ena får den att leta efter kod, den
andra att skriva den.

Slog mig att det här troligen är värre med AI-agenter än med
mänskliga läsare. En människa som läser en dokumentation som inte
stämmer antar att dokumentationen är gammal. Agenten antar att den
själv har missat något och börjar leta.

## 2026-09-06

Steg 2 blev renare genom att `kind="outcome"` flyttades till steg 3, 
påståendet kunde verifieras mot exakt det trädet.

Landade i minnesprojektet efter att ha vägt det mot Tokeniser.
Avgörande: LongMemEval finns redan, så jag slipper bygga eget
dataset och evalen blir trovärdig.

Överraskning: prototypen behöver inte vara klar. Utvärderingen kör
minnet headless, agenten är bara demo. Det tog mig ett tag att fatta.

Osäker på: om chat_json går att anropa utan verktygsloopen. Ska kollas.