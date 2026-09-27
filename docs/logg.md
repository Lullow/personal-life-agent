# Labbjournal — minnesprojektet

Senaste överst. Vad jag gjorde, vad jag fick, vad som förvånade mig.

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

Jag insåg också att ett modellbyte inte betyder att modellen "glömmer projektet" på det sätt jag först tänkte.
Varje anrop är redan tillståndslöst. Det jag egentligen riskerar att förlora är hur väl p
inte själva arbetet.

Kostnaden hittills är nästan noll; piloten beräknas kosta under $0,50, ungefär fem kronor.
Det dyrare steget blir M3 och konsolideringen.
Jag funderade på lokala modeller på min 3090, men valde bort det eftersom det skulle bli
och rättningen ändå behöver göras med GPT-4o för att resultaten ska vara jämförbara.

Det som fortfarande är öppet är bland annat i vilken ordning RetrievalMemory ska ge historiken till modellen (M2),
om svarsprompten i 0008 håller när den testas, vilken modell som ska användas för konsolideringen i M3 
och vilket statistiskt test som passar bäst.

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