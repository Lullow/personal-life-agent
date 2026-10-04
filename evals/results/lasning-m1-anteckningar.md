# M1-läsning: författarens anteckningar (pilot `recent-turns-20260927-132525`)

> Läsningen gjordes 2026-09-27. Jag läste svaren själv och gav min bedömning,
> en AI-assistent (Claude i chatt) gav sin, och vi kom fram till en gemensam
> slutsats. Texten nedan är renskrivningen som lämnades till Claude Code, med
> överlämningens "Gör så här" kvar. Sparad som fil i efterhand 2026-10-04, ur
> chatten. Genomgången som skrevs utifrån den är
> `recent-turns-20260927-132525-review.md`.
>
> (English: the author's reading notes for the M1 pilot, in Swedish; read
> 2026-09-27, categories agreed in dialogue with an AI assistant, saved as a
> file on 2026-10-04. The review derived from it is in this directory.)

Jag har läst 0f05491a och alla 20. Svar på din fråga: den senare evidensturen
(answer_d6d2eba8_2:6) var i kontexten och säger uttryckligen "120 stars, not 300".
Facit stämmer. Modellen svarade ändå 300, vilket är Starbucks verkliga gamla regel.
Alltså: kontext ignorerad till förmån för träningsdata, inte ett retrieval- eller datafel.

Fördelning över alla 20:
- 17 evidens saknades (ingen evidenstur i kontexten, modellen svarade "I do not know" i samtliga)
- 2 kontext använd, rätt svar (b6019101, 6aeb4375; båda breakdown=later, 6,3k resp 1,7k tokens bort)
- 1 kontext ignorerad (0f05491a, later, 3,7k bort)
Alla tre "reached" ligger inom 6,3k tokens; alla 17 missar ligger ≥10k bort.
Ingen av de tre later-frågorna hade båda evidensturerna i kontexten, så "both" är otestat.

Datanoteringar (påverkar inte baslinjen, men ska kontrolleras i M2/M3):
- 51a45a95: markerad evidenstur (4) nämner inte Target; svaret kräver tur 2 i samma session
  och är en inferens. Risk för turbaserad retrieval: reached=True utan att svaret finns.
- c6853660: senare tur säger "thinking of changing to two cups", facit säger "you increased".
- a2f3aa27: senare tur säger "close to 1300", facit säger 1300.
- 89941a94: frågan säger "gravel bike", evidensen säger "hybrid bike".
- b01defab: evidensturerna utanför fönstret, men tre meddelanden från den senare sessionen
  låg kvar och diskuterar bokens slut. Modellen svarade ändå vet ej.

Gör så här:
1. Skriv ner detta som data/longmemeval/reading-recent-turns-20260927-132525-review.md
   (eller det filnamn guiden anger), med tabellen per fråga och noteringarna ovan.
2. Committa, och pusha alla fyra commits.
3. Berätta sedan vad kostnadsavstämningen gav och vad piloten kostade per fråga,
   så att vi kan sätta N enligt steg 1 i planen.
