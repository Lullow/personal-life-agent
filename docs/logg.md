# Labbjournal — minnesprojektet

Senaste överst. Vad jag gjorde, vad jag fick, vad som förvånade mig.

## 2026-09-06

Steg 2 blev renare genom att `kind="outcome"` flyttades till steg 3, 
påståendet kunde verifieras mot exakt det trädet.

Landade i minnesprojektet efter att ha vägt det mot Tokeniser.
Avgörande: LongMemEval finns redan, så jag slipper bygga eget
dataset och evalen blir trovärdig.

Överraskning: prototypen behöver inte vara klar. Utvärderingen kör
minnet headless, agenten är bara demo. Det tog mig ett tag att fatta.

Osäker på: om chat_json går att anropa utan verktygsloopen. Ska kollas.