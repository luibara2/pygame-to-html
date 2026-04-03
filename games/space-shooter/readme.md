# Vesmírná střílečka

Rychlá arkádová hra v pygame: vyhýbej se ztrátě životů, nič meteority a hlavně nestřílej astronauty.

## Spuštění

1. Nainstaluj závislosti:
	- `pip install pygame numpy`
2. Spusť hru:
	- `python main.py`

## Ovládání

- Šipka vlevo / vpravo: pohyb raketky
- Mezerník: běžná střelba (můžete mačkat nebo držet)
- Šipka nahoru: nabitá salva (3 rány)
- Esc: pauza
- F11: přepnutí celé obrazovky
- Enter / myš: potvrzení v menu

## Jak hrát

- Kolo začíná až po prvním pohybu raketky.
- Nič meteority, aby ses vyhnul ztrátě životů a získával body.
- Když meteorit prolétí spodem obrazovky, ztratíš 1 život.
- Astronauti, kteří jen prolétnou, ti neublíží.
- Pokud ale zasáhneš astronauta střelou, hra okamžitě končí.
- Po zhruba 30 sekundách se objevují velké červené meteority.
- Velký meteorit vydrží 3 zásahy.
- Po každých 5 zničených meteoritech nabiješ speciální salvu.
- Nabitá salva se aktivuje šipkou nahoru a vystřelí 3 rány naráz.

## Power-upy

Power-upy padají shora přibližně každých 20-30 sekund. Aktivují se tak, že zasáhneš jejich ikonu střelou.

- S: Štít (8 s)
- T: Zpomalení času (10 s)
- B: Zrychlení (10 s)

## Žebříček

- Po konci hry můžeš zadat tříznakové iniciály.
- Výsledky se ukládají do souboru `leaderboard.jsonl`.