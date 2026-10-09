# Labbjournal — minnesprojektet

Senaste överst. Vad jag gjorde, vad jag fick, vad som förvånade mig.

## 2026-10-07

Sent igår kväll och i förmiddags: provade det som ska visas i Neo4j och
tog skärmbilderna.

Frågorna mot grafen fungerar. Kedjan för kaffet visar att en kopp
ersattes av två, och frågan mot en tidpunkt ger en kopp 26 maj och två
koppar 27 maj.

Provet hittade två fel i bildspelet. Det viktigaste: rådet under "Om
något går fel" hade alltid gett ett tomt svar, så det hade inte hjälpt
på fredag. Båda är rättade.

Tog sedan skärmbilder som reserv: fem av kedjan i Neo4j och två av
agentdemon. Demon fick jag göra om tre gånger. En gång körde jag utan
DB_PATH, och då visades min riktiga databas med privata händelser. Den
bilden kastades.

Bra att tänka på inför fredag: Neo4j startar inte av sig självt efter en
omstart av datorn, det hände två gånger. Och demon måste köras mot
demodatabasen, annars syns mina egna händelser på den delade skärmen.

Kvar: torsdag två genomkörningar med klocka, grenen ihop med main och
repot till Gabriel.

---

Eftermiddagen: gick igenom bildspelet mot repot en gång till.

Siffrorna stämde, men småsaker hade glidit isär. Körschemat pekade på en
fil som inte skulle finnas, eftersom jämförelseskriptets argument stod i
en annan ordning än i docs/presentation.md och filnamnet följer
ordningen. Och en rad på första bilden var en förenkling, inte det
kommandot faktiskt skriver ut.

Bra att tänka på: allt som ska köras eller öppnas live måste
kontrolleras mot repot, inte bara resultaten.

Reservplanen pekar nu ut bilderna med filnamn, så att jag inte behöver
leta om något går fel.

## 2026-10-06

Mätningen är klar. Kvar är redovisningen på fredag och det skrivna som
Gabriel bad om: en översikt med syfte och resultat, och ett tydligt
ställe att börja läsa på.

Jag hade ett bildspel med körschema som byggdes i en annan chatt, utan
tillgång till allt i repot. Lät agenten kontrollera det mot
resultatraderna och dokumenten. Huvudsiffrorna stämde: tabellerna, de
tre exempelfrågorna och kostnaden. Men tolv saker avvek, och de är inte
rättade än.

Den viktigaste: körschemat sa att Gabriel inte hade svarat om en skriven
rapport. Det hade han. Ingången i README och avsnittet om avvikelser är
alltså nödvändiga, inte bara bra att ha.

**Anledning** till ordningen: jag började med de två, eftersom det är
det Gabriel uttryckligen kräver.

README har fått ett nytt första avsnitt om VG-projektet: frågan, vad som
byggdes, resultaten, metoden och en läsordning genom repot.
Kontrollskriptet räknar nu om README:s siffror också. docs/vg-project.md
har fått ett avsnitt om var projektet avviker från pitchen, och
körordningen är omskriven efter bildspelet: nio delar på 30 minuter.

Två avvikelser skrev jag skälen till själv. Latens: ingen mätregel skrevs
och ingen rad mäter tid, och mer än så säger jag inte. Datasetet: tanken
var att mitt eget skulle växa fram medan jag byggde agenten under
terminen, och det blev aldrig av. Därför blev LongMemEval det självklara
valet.

Granskningen hittade också ett fel i rapporten. Den säger att
anteckningarna höll det nya värdet i alla 20 rätta svar på ändrade
fakta. Enligt mina läsanteckningar gäller det 16 av 20. Inte rättat än.

Bra att tänka på: agenten gjorde fyra val som jag inte har bestämt,
bland annat var de nya avsnitten ligger. Och planen är exakt 30 minuter,
utan tid för frågor.

Kvar: committa, rätta bildspelet och meningen i rapporten, och två
genomkörningar med klocka på torsdag. Torsdag slås grenen ihop med main,
så att Gabriel ser rätt README.

---

Kvällen: bildspelet rättat, och ett stöd för själva framförandet.

Agenten gick igenom bildspelet punkt för punkt mot repot innan något
ändrades. Avvikelserna från tidigare idag är rättade, utom två. Planen
är fortfarande 30 minuter utan tid för frågor. Och en av granskningens
punkter var själv fel: testraden var den som bildspelet sa.

Jag ställde fyra frågor, och två svar är värda att komma ihåg.
Bildspelet påstod att jag hade skrivit tolkningar i förväg för varje
tänkbart utfall. Det finns inget sådant i repot, och jag känner inte
igen det, så meningen är struken. Och budgeten på 8 000 tokens
räknades aldrig fram. Talet lades in i koden 6 september som ett väl
tilltaget tak för planerarens minne, och ADR 0006 låste det för alla
strategier innan något mättes. I efterhand är nivån rimlig av tre
skäl. Den är bara 8 % av en historik, så minnet måste välja: i 105 av
122 frågor ligger svaret utom räckhåll för de senaste turerna. Den är
mer än planeraren själv använder, eftersom tio replikskiften blir som
mest knappt 7 000 tokens i testsamtalen. Och den håller kostnaden
nere. Men varför just 8 000 står ingenstans, och jag har bara mätt en
budget.

Felet i rapporten från tidigare idag är rättat: 16 av 20, inte alla 20.
Det slank igenom för att kontrollskriptet inte hade något påstående för
just den meningen. Nu har det det.

Bra att tänka på: 30 minuter är en utgångspunkt, inte skrivet i sten.

Kvar: läsa manuset och klicka igenom bildspelet, kostnaden i kronor och
skärmbilderna. Torsdag: två genomkörningar, ihop med main och repot till
Gabriel.

---

Senare på kvällen: kostnaden i kronor, och en dollarsumma som var fel.

Rapporten ska säga vad mätningen kostade i kronor, framräknat av ett
skript. När skriptet skrevs visade det sig att dollarsumman i
docs/vg-project.md var fel. Där stod 26,90 dollar när M3 stängdes och
28,73 efter M4. Rätt är 19,13 och 20,96.

Felet uppstod 4 oktober, i en räkning som agenten gjorde en gång utan
skript. Kontot hade använt 8,65 dollar innan riggen gjorde sitt första
anrop, och det mesta av det räknades med av misstag. Det upptäcktes när
riggens egen räkning över alla sparade rader gav 19,56 dollar, långt
under 28,73.

Rätt siffror: mätningen har kostat 20,96 dollar, ungefär 280 kr med det
jag faktiskt betalade per dollar (13,34 kr). Det är 28 % av taket på
1 000 kr. De tre strategierna kostade 19,13 dollar, vilket ligger inom
uppskattningen i ADR 0010.

Rättelse av loggen: 4/10 skrev jag ungefär 359 kr och 5/10 28,73 dollar.
Båda byggde på den felaktiga summan.

Siffran hade hunnit sprida sig till bildspelet, sammanfattningssidorna
och kartan. De är rättade. ADR 0019 citerar den gamla summan och står
orörd, eftersom en ADR aldrig ändras. Beslutet där vilade inte på talet.

Bra att tänka på: en siffra som inte räknas av ett sparat skript kan
vara fel i flera dagar utan att någon märker det. Det skrev jag redan
26/9, och det gällde fortfarande.

Kvar: ta bort "(draft)" i rapporten, skärmbilderna och torsdagens
genomkörningar.

## 2026-10-05

Godkände körordningen för redovisningen, så första steget i M4 är klart.
Satte sedan upp Neo4j i Docker.

Förmiddagen gick till spiken, ett prov inför ADR 0018 som inte mäter
något: inga frågor besvaras och inget rättas. Varje session skickas till
gpt-4o-mini, som plockar ut fakta som tripplar (vem, relation, värde),
och de ritas in i grafen. Provet kördes på de åtta KU-historiker som
inte ingår i mätningen, i tre rundor med olika regler för hur ett gammalt
värde ersätts.

Runda 1, inget ersätts: 1 342 fakta, men modellen kallar inte samma sak
samma namn i två sessioner. Runda 2, modellen pekar själv ut vad som
ersätts: 8 ersättningar, och ingen gällde det värde frågan handlar om.
Runda 3, koden ersätter när vem och relation är samma: 74 ersättningar,
men bara 1 gick från en evidenstur till en annan (väckningstid 8:30 till
7:30).

Agentens läsning är att det går bra att plocka ut fakta: det nya värdet
kom med i alla åtta historiker. Det svåra är att ersätta rätt. Ungefär
56 av de 74 ersättningarna är olika saker som fått samma allmänna namn,
till exempel recent_activity. Det är en bedömning, inte räknat.

Det som inte gick som planerat: regeln som guiden gissade på före provet
var den som fungerade minst dåligt, men den ersätter fel oftare än rätt.
Och grafen blev en stjärna runt användaren, inte ett nät.

Bra att tänka på: agenten körde runda 3 utan att fråga först (0,21
dollar). Jag bad sedan om en kontroll av regeln efter fallgropar, utan
modellanrop. Den hittade fyra problem, med ett förslag till lösning på
vart och ett. Ett av dem är att regeln ersätter fakta som inte hör ihop.

Tog sex skärmbilder av grafen som reserv till fredag. En av dem visar en
fråga mot en tidpunkt: 25 maj gäller 8:30, 28 maj gäller 7:30. Det är
det pitchen kallade facit vid varje tidpunkt, visat på ett exempel men
inte mätt.

Provet kostade 0,60 dollar. Vilken regel som går in i ADR 0018 är inte
bestämt än. Agenten rekommenderar regeln från runda 3 med de fyra
lösningarna.

Kvar: M4 in i docs/vg-project.md, ADR 0018 och 0019. Tisdag: bygget,
testerna och röktestet.

---

Efter lunch: planen och ADR:erna för faktagrafen.

Jag valde regeln från runda 3 med de fyra lösningarna från
fallgropskontrollen. M4 står nu i docs/vg-project.md med tre stopp
(måndag, tisdag och onsdag kväll) och en strykordning.

Agenten skrev utkast till två ADR:er, och jag läste dem och lämnade
ändringar i fyra omgångar. ADR 0018 beskriver grafens design: ett nytt
värde ersätter det gamla när vem och relation är samma, och det ersatta
raderas inte utan märks med tid. ADR 0019 säger att grafen mäts som en
pilot på 20 frågor i en egen tabell.

Jag läste själv de 8 ersättningarna från runda 2: 1 var rätt, 1 var
samma värde med mer detalj och 6 var fel.

Ett beslut jag vill vara ärlig med. Runda 2:s prompt höll namnen
stabilare, så frågan var om den borde användas i stället. Min gräns för
att byta: värdet ersätts i minst 4 av 8 och färre än 4 evidensfakta
döljs. Jag bestämde den innan uppspelningen kördes, men skrev inte ner
den förrän jag hade sett resultatet. Utfall: 5 av 8 (ja) och 4 av 69
(nej). Runda 3 står kvar.

Bra att tänka på: prompten jag behåller klarar inte heller gränsen. Den
gällde ett byte, eftersom runda 2:s prompt inte går att använda som den
är, och underlaget bara är en körning per prompt på åtta historiker.

Ett nytt skript räknar om siffrorna i båda ADR:erna utan modellanrop: 69
stämmer, 10 kommer utifrån och 0 avviker. Ett par siffror i guiden gick
inte att återskapa och är rättade.

Svagheten står utskriven i ADR 0018: överskrivningen träffade det
ändrade värdet i bara 2 av 8 historiker.

Kvar: committa, sedan bygget på tisdag. Är klassen, testerna och
röktestet inte klara tisdag kväll mäts ingen pilot.

---

Eftermiddagen: bygget och piloten, en dag tidigare än planerat.

FactGraphMemory är byggd, med ett lager i Neo4j och ett i processen för
tester och torrkörning. 421 tester är gröna. De två första strategierna
torrkördes om på alla 122 frågor och gav samma rader som förut, så inget
gammalt har ändrats.

Jag bad om en dubbelkoll före commit. Den hittade ett trasigt skript och
två meningar som lät som om piloten redan var mätt.

Bra att tänka på: när agenten provade att alla skript gick att importera
råkade ett av dem köras, och det skrev över två filer under data/. Jag
minns inte att jag hade skrivit något för hand i dem. Skriptet har fått
ett skydd så att det inte kan hända igen.

Sedan mätningen. Rökprovet på en fråga per typ gick utan fel. Piloten
kördes 16:16–16:29: 20 frågor, 1 475 anrop, inget misslyckat. Riggen
räknar 1,18 dollar, och saldot sjönk 1,15.

Utfallet är inte läst än. Enligt ADR 0019 redovisar jag ingen siffra
förrän jag har läst svaren för hand.

En sak syntes redan i rökprovet: det gamla och det nya värdet fick olika
namn, så inget ersattes och båda visades. Det är svagheten som ADR 0018
varnade för.

Agenten gjorde också sju val där ADR 0018 är tyst. Jag sa att det såg
bra ut, men jag har inte gått igenom dem ett och ett.

Kvar: läsa de 20 svaren, pilottabellen, stycket i docs/method.md och att
stänga M4.

---

Läsfilerna för piloten är klara. En har alla 20 svar i en tabell bredvid
facit, domarens utslag och de tre andra strategiernas svar. Två har
frågorna uppdelade efter om svaret blev rätt eller fel, med det som
visades för modellen per fråga. Utfallet är oläst tills jag har läst dem
för hand (ADR 0019).

---

Kvällen: läsningen av pilotens 20 svar, och sedan stängdes pilotdelen av
M4.

Läsningen gick till så att AI-assistenten läste alla 20 svar först. Jag
bedömde sju själv och kontrollerade de tretton andra mot dess rader.
Mina anteckningar prövades sedan mot resultatraderna: 158 av 161
påståenden stämde. Anteckningarna står kvar orörda, och genomgången
följer raderna.

Där jag hade fel: jag räknade att värdet fanns bland de visade fakta i
18 av 20 frågor, raderna ger 17. Och tre frågor gäller själva ändringen,
inte två.

Resultatet enligt domaren: faktagrafen fick 10 av 10 på de vanliga
frågorna och 6 av 10 på ändrade fakta (5 av 10 om man ser till
innehållet). På samma 20 frågor fick baslinjen 0 och 3, sökningen 9 och
6, och sammanfattningen 4 och 3. Piloten rangordnar inte strategierna,
en enda fråga är 0,1.

Det jag förstår är att de fyra felen sitter på fyra olika ställen:
utdraget, regeln, modellens svar och ett som var nästan rätt. Regeln
ersatte det gamla värdet med det nya i sex av tio frågor om ändrade
fakta, och varje gång rätt. Men enligt agentens läsning gäller 45 av de
70 ersättningarna en annan sak under samma namn.

Bra att tänka på: på vägen hittades två fel i äldre genomgångar. De har
fått daterade rättelser, och originaltexten står kvar.

Pilotdelen av M4 är stängd, två dagar före det hårda stoppet. Körningen
på alla 122 frågor görs inte, och grafen kopplas inte till agenten. I
stället visas kedjan direkt i Neo4j. Kostnaden hittills är 28,73 dollar.

Kvar till tisdag: körordningen och de tre frågorna ska in i repot, och
jag ska bestämma var reservbilderna ska ligga.

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