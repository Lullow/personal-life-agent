# M2-läsning: författarens anteckningar (`retrieval-20261002-193417`, `recent-turns-20261002-193902`)

> Läsningen gjordes 2026-10-03. Jag läste svaren själv och gav min bedömning,
> en AI-assistent (Claude i chatt) gav sin, och vi kom fram till en gemensam
> slutsats. Texten nedan är renskrivningen som lämnades till Claude Code.
> Sparad som fil i efterhand 2026-10-04, ur chatten. Genomgången som skrevs
> utifrån den, och som kontrollerades mot raderna och datasetet, är
> `m2-runs-20261002-review.md`.
>
> (English: the author's reading notes for the M2 runs, in Swedish; read
> 2026-10-03, categories agreed in dialogue with an AI assistant, saved as a
> file on 2026-10-04. The review derived from it is in this directory.)

Här är mina anteckningar från handläsningen av M2 (2026-10-03). Jag läste
filerna själv och diskuterade bedömningarna med en AI-assistent (Claude i chatten).
Jämför gärna med din egen preliminära sortering av steg 1 och 2 och visa var vi
skiljer oss.

Bokstäver: A = svarade med det gamla värdet, B = "I do not know" fast svaret fanns,
C = annat fel svar, D = domarfel. (E) = evidens eller facit otydligt i datat.

STEG 1: ändrat faktum, båda värdena framme, fel (13)
07741c45  A  under bed → shoe rack; svarade "under your bed". Senare turen otydligt skriven (E?)
6071bd76  C  6 oz → 5 oz; angav ordningen rätt men drog slutsatsen "more water"
a2f3aa27  B  1250 → "close to 1300"; nya värdet vagt i datat (E)
0f05491a  B  125 → 120; fyra olika tal i evidensen (400, 125, 300, 120)
c4ea545c  B  3 dagar → 4 ggr/vecka; såg bara det gamla, sa att jämförelse saknas. Gränsfall mot A
69fee5aa  A  37 → 38; svarade 37. Nya värdet står aldrig utskrivet, kräver 37+1
59524333  A  7:00 pm → 6:00 pm; svarade 7:00 pm
7401057b  B  en natt → två
852ce960  A  350k → 400k; svarade 350k. Senare turen är en tillbakablick, ingen ändring (E?)
1cea1afa  B  500 → 600
ba61f0b9  A  5 → 6 kvinnor; svarade 5
f685340e  C  varje vecka → varannan; satte "every other week" som tidigare, missade "weekly"
4b24c848  A  3 → 5; svarade 3
Summa: 6 A, 5 B, 2 C, 0 D.

STEG 2: faktafrågor, evidensen framme, fel (9)
51a45a95  C  svarade "last Sunday from your email inbox"; evidensturen nämner inte Target (E)
545bd2b5  B  evidensen säger "around 2 hours"
60d45044  B  evidensen säger "my favorite Japanese short-grain rice"
b86304ba  B  evidensen säger "flea market find", inte "painting of a sunset" (E)
311778f1  B  evidensen säger "I think I spent 10 hours"
6ade9755  B  evidensen säger "can't make it to Serenity Yoga"
76d63226  B  evidensen säger "new Samsung 55-inch"
1faac195  B  evidensen säger "my sister Emily in Denver"
118b2229  B  evidensen säger "45 minutes each way"
Summa: 8 B, 1 C, 0 D. I sju av de åtta B stod svaret ordagrant i evidensturen.

STEG 3: baslinjen rätt utan evidens (2)
b01defab  ingen gissning: andra turer ur samma samtal i kontexten diskuterar bokens slut
603deb26  troligen ingen gissning: 8 meddelanden ur samma samtal i kontexten; syns inte i filen var "10" står

STEG 4: sökningens övriga fel (3)
75499fd8  evidensturen delar inga ord med frågan ("Golden Retriever" mot "breed", "dog")
25e5aa4f  omskrivning: "completed", "undergrad", "CS" mot "complete", "Bachelor's degree", "Computer Science"
0977f2af  frågan gäller det tidigare värdet; turen om Instant Pot delar nästan inga ord med frågan
I alla tre var modellens "I do not know" rimligt. Felen är lexikala missar i sökningen.

STEG 5: skumläsning av alla svar
Ingen instruktionskapning i någon av körningarna. Inga domarfel.
50635ada  rätt, men formulerat som slutledning ("would have been Premier Silver")
0f05491a  baslinjen svarar ur träningsdata (300 stjärnor, 12 månader), som i piloten
853b0a1d  baslinjen: "vet inte" med andra ord, rätt bedömt

KONTROLLFRÅGOR TILL DIG
1. 51a45a95: fanns answer_d61669c7:2 i sources? Det avgör om Target stod i kontexten.
2. 603deb26 (baslinjen): i vilken tur bland answer_8afdebac_2:4–11 står "10"?
3. 50635ada: fanns den tidigare evidensturen i kontexten, eller bara den senare?
4. Är 07741c44/07741c45 och 89941a93/89941a94 systerfrågor om samma faktum?

Skriv genomgången i evals/results/ utifrån detta, och ändra inget i mätningen.
