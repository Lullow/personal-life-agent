# Labbjournal — minnesprojektet

Senaste överst. Vad jag gjorde, vad jag fick, vad som förvånade mig.

## 2026-10-04

Körningen av den tredje strategin (sammanfattning) blev klar under
natten. Läste igenom alla 122 svar själv och sorterade dem efter varför
de blev rätt eller fel, och jämförde sedan med agentens sortering.

Resultatet blev sämre än jag trodde. Sammanfattningen fick 14 av 61 rätt
på de vanliga frågorna och 20 av 61 på frågorna där ett faktum har
ändrats. Sökningen fick 50 och 47. Hypotes 3 höll alltså inte:
sammanfattningen kostar ungefär fyra gånger så mycket per fråga, men den
missar fler ändrade fakta, inte färre.

Det jag förstår av läsningen är att modellen som sammanfattar läser rätt
session, men sällan skriver ner just det faktum som frågan sedan gäller.
När faktumet väl stod i anteckningarna blev svaret nästan alltid rätt
(26 av 28). Annars svarade modellen oftast "I do not know".

Jag trodde att sammanfattningen skulle vara bäst på ändrade fakta,
eftersom den hela tiden skriver om sig själv. Men små detaljer försvann
ofta när runt 50 sessioner skulle pressas in på cirka 1 000 tokens.

Bra att tänka på: jag hade själv fel på ett par ställen när min
sortering jämfördes med resultatraderna. Därför beskriver jag läsningen
i rapporten som gjord i dialog med agenten, inte som två oberoende
läsningar.

Läste igenom ADR 0016 och 0017, som agenten skrev medan jag sov, och
behåller dem. 0016 känns rimlig eftersom en trasig session annars slår
ut hela frågan för alla tre strategierna. 0017 följer tanken med en
rullande sammanfattning genom att behålla det nyaste. Däremot kan den
missgynna äldre fakta, så det tas upp som en begränsning i rapporten.

M3 är stängd, två dagar före planeringen. Kontrollen med gpt-4o är valfri
(ADR 0010), och kräver ny kod i riggen - jag har valt att inte göra den.
Tabellens och analysens siffror står i docs/results.md.

Begränsningen från 27/9 står därför kvar: jag kan inte säga om det svaga
resultatet beror på metoden eller på den mindre modellen.

Kvar: rapporten, som ska in 9 oktober. M3 blev klar i tid, så M4 är
fortfarande ett alternativ. Beslutet tar jag måndag 5 oktober, när jag
har vägt nyttan av en andra benchmark eller modell mot tiden som är kvar
till analys och rapport.

---

Kvällen gick åt till planering. Ingen kod skrevs.

Räknade om kostnaden till kronor. Jag har betalat 800,25 kr för 60
dollar i krediter, ungefär 13,34 kr per dollar. ADR 0010 räknade med
9,90 kr, så det blev runt 35 % dyrare (moms, bankens kurs och avgift).
Mätningen har hittills kostat ungefär 359 kr av taket på 1 000 kr.

Jämförde sedan projektet med pitchen till Gabriel från 10 september. Det
mesta håller, men tre saker saknas: strategin med tidsstämplade fakta
som skrivs över, latens, och grafdatabasen som Gabriel föreslog. En sak
jag mindes fel: vektorsökningen ströks inte för att den var dyr, utan
för att den krävde fler mätregler och M2 redan låg på sitt slutdatum
(ADR 0011).

Examinationen är en redovisning på 30 minuter med skärmdelning, fredag
9 oktober. Jag var orolig för att mitt innehåll mest ligger i text, men
det mesta går att visa direkt ur repot. Jag har skrivit till Gabriel för
att kolla att jag har förstått hans förslag rätt.

Beslutet om M4 kom redan i kväll: en fjärde strategi, en faktagraf i
Neo4j, där ett nytt värde ersätter det gamla utan att det raderas.

**Anledning**: den täcker både strategin jag lovade i pitchen och
Gabriels förslag.

Grafen mäts som en pilot på 20 frågor, och jämförelsen på 122 frågor är
fortfarande huvudresultatet. Redovisningen går först, och onsdag kväll
är hårt stopp.

Öppet: Gabriels svar, varför latens inte mättes, och hur kronkostnaden
ska redovisas.

---

Senare på kvällen började jag ändå med första steget i M4: att säkra
redovisningen, så att den fungerar även om inget mer blir gjort.

Det gamla läsningsskriptet räckte inte. Det ger en fil per körning på
över 500 rader, och tre minnen går inte att jämföra på en delad skärm.
Därför gjorde jag ett nytt skript som visar en fråga genom alla
strategier sida vid sida. Det läser bara sparade rader och anropar ingen
modell, så det behöver ingen ADR.

Valde tre frågor att visa, en per hypotes. Nike-frågan: baslinjen svarar
"I do not know", de två andra rätt. Frågan där tre toppar blev fem:
sökningen hade båda värdena framför sig och svarade det gamla. Frågan
där Ford Mustang blev Ford F-150: sammanfattaren läste rätt session, men
värdet finns inte kvar i anteckningarna.

Bra att tänka på: tre frågor är exempel, inte bevis. När jag visar dem
säger jag också proportionerna, 20 mot 47 av 61.

Körde agentdemon mot en egen databas och lade till en glömskescen: jag
säger att mina favoritlöparskor är Nike, startar om, och agenten vet
ingenting. Det är samma fråga som sedan går genom de tre minnena.
Utskrifterna i docs/demo.md är omskrivna från riktiga körningar,
eftersom agenten betedde sig lite annorlunda än dokumentet sa.

Hittade ett fel på vägen: bekräftelsefrågorna i chatten visade inte
[y/N], eftersom Rich läste hakparentesen som formatering. Rättat, 357
tester gröna.

Gabriel svarade att planen låter rimlig men beror på detaljerna, så den
ändras inte. Frågan om en skriven rapport fick jag inget svar på, så jag
har frågat igen.

Kvar: tiderna i körordningen (utkastet landar på 27–37 minuter mot 30),
och sedan testet med tripplar in i Neo4j.

## 2026-10-03

Läste själv igenom de 27 svar som avgör hypoteserna och skummade alla
244. Jämförde min bedömning med agentens. På tre frågor tyckte vi olika,
och där höll min.

Det läsningen visade: sökningen hittar nästan alltid rätt ställe i
samtalet. Av dess 25 fel hade 23 svaret framför sig. Felen ligger alltså
hos modellen som svarar, inte hos minnet. Ofta svarade den "I do not
know" fast svaret stod där, och ibland valde den det gamla värdet fast
det nya också fanns med.

Hypotes 1 håller. Hypotes 2 håller till hälften. Sökningen hittar gamla
fakta mycket bättre än baslinjen (50 mot 3 rätt). Men att den skulle
svara sämre när ett faktum har ändrats syns inte tydligt: 47 mot 50 är
för liten skillnad för att säga något.

Skrev sedan metodavsnittet och stängde M2, en dag sent. Resultaten står
i docs/results.md.

---

På kvällen började jag med M3, den tredje strategin: en sammanfattning
som skrivs om efter varje session (ADR 0012–0014). Jag godkände
upplägget och bad agenten gå igenom fallgroparna innan något byggdes.

Första testet sprack. Modellen som sammanfattar brydde sig inte om
ordgränsen, och sammanfattningen blev större än hela budgeten.

**Anledning** till lösningen: jag valde ett tak i koden. Modellen får en
chans att korta texten, och är den fortfarande för lång klipps den
(ADR 0015).

Sedan lät jag agenten arbeta vidare över natten. Två beslut togs medan
jag sov (ADR 0016 och 0017): vad som händer när modellen fastnar i en
loop, och från vilket håll texten klipps.

## 2026-10-02

Började med en avstämning. M1 skulle ha varit klar 29 september, men jag
hade inte gjort något sedan 27:e. Stängde M1 tre dagar sent och flyttade
metodavsnittet till M2.

Bestämde hur sökningen ska fungera: BM25 i stället för embeddings
(ADR 0011). Det jag förstår är att BM25 letar efter turer som delar ord
med frågan.

**Anledning**: BM25 behöver inga modellanrop. Det kostar inget att
testa, och siffrorna går att räkna om utan nyckel. Nackdelen är att den
bara matchar ord som stavas lika.

Ett beslut som var viktigare än jag först trodde: turerna visas i den
ordning de sades. Modellen ser inga datum, så ordningen är det enda som
visar vilket värde som är nyast.

Byggde RetrievalMemory och testade först utan modellanrop. Sökningen
hittar rätt ställe i 59 och 61 av 61 frågor, baslinjen i 6 och 11.
Körde sedan på riktigt, 122 frågor per strategi. Sökningen fick 50 och
47 av 61 rätt, baslinjen 3 och 9.

Bra att tänka på: samma fråga fick "I do not know" första gången och
rätt svar andra gången, med exakt samma indata. Modellen svarar alltså
inte alltid likadant, även vid temperatur 0.

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