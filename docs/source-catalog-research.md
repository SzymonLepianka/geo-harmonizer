# Katalog źródeł — metodyka i stan weryfikacji

Data kontroli: **30 czerwca 2026 r.**

Katalog służy do zapewnienia reprodukowalności pracy badawczej. Sam fakt technicznej dostępności usługi nie oznacza, że dane są rozstrzygnięciem prawnym ani że wszystkie atrybuty źródłowej bazy są publiczne. LPIS pozostaje źródłem pomocniczym względem EGiB.

## Metodyka

1. Adres i zakres potwierdzono na stronie właściwego organu publicznego.
2. Dla WFS wykonano `GetCapabilities` i odczytano wersję oraz nazwy warstw.
3. Dla małego obszaru Żywca wykonano `GetFeature` lub `resultType=hits`.
4. Sprawdzono format odpowiedzi, kolejność osi BBOX i możliwość odczytu przez GeoPandas/Fiona.
5. Usług niepotwierdzonych nie oznaczono jako automatyczne.

## Zweryfikowane profile

| Źródło | Dostęp | Profil techniczny | Stan |
|---|---|---|---|
| GUGiK EGiB — działki i budynki | automatyczny | WFS 2.0, GML, osie YX, `ms:dzialki`, `ms:budynki`, limit 1000 | działał dla ograniczonego BBOX |
| Powiat Żywiecki EGiB | automatyczny | WFS 1.1, GML, osie YX, `ms:dzialki`, `ms:budynki` | działał |
| ARiMR LPIS działki referencyjne | automatyczny | WFS 2.0, GeoJSON, osie XY | działał |
| ARiMR LPIS MKO | automatyczny | WFS 2.0, GeoJSON, osie XY | działał |
| ARiMR LPIS pokrycie terenu | automatyczny | WFS 2.0, GeoJSON, powierzchnie | działał |
| ARiMR GSA 2025 | automatyczny | WFS 2.0, osobne warstwy upraw, gruntów ornych i TUZ | działał |
| ARiMR GSA 2026 — woj. śląskie | ręczny | publiczna paczka SHP, ok. 95 MB | pobieranie działało |
| BDOT10k — powiat żywiecki | ręczny | GML 2021, ok. 125 MB | pobieranie działało |
| BDOT500/GESUT Żywiec | zamówienie | Portal Interesanta PZGiK | brak publicznego pobierania potwierdzonego |
| PRG | wyłączony | oficjalny WFS | `GetCapabilities` zwracał HTTP 502 |

Ponowny smoke-test PRG wykonany później tego samego dnia zwrócił poprawne
`GetCapabilities` z 52 typami warstw. Profil pozostaje wyłączony: pojedyncza
odpowiedź nie potwierdza jeszcze stabilności ani kompletnego `GetFeature` dla
wybranego poziomu granic.

Zbiorczy WFS EGiB GUGiK ogranicza pojedynczą odpowiedź do 1000 obiektów, a jego
stronicowanie `startIndex` zwracało niespójne liczebności. Katalog dlatego
blokuje większe zakresy dla tego źródła i kieruje badanie powiatowe do
bezpośredniego WFS właściwego powiatu.

## Oficjalne punkty odniesienia

- [EGiB i zbiorczy WFS GUGiK](https://www.geoportal.gov.pl/pl/dane/ewidencja-gruntow-i-budynkow-egib/)
- [Publiczne dane LPIS i GSA ARiMR](https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow)
- [BDOT10k i sposoby pobierania](https://www.geoportal.gov.pl/pl/dane/baza-danych-obiektow-topograficznych-bdot10k/)
- [Państwowy Rejestr Granic](https://www.geoportal.gov.pl/pl/dane/panstwowy-rejestr-granic-prg/)
- [Portal Interesanta Powiatu Żywieckiego](https://mapy.zywiec.powiat.pl/)
- [Raport usługi EGiB powiatu żywieckiego](https://wms16.epodgik.pl/walidator/data/files/reports/2025_04_10/raport_wfs_2417_2025_04_10.pdf)

## Zasady eksploatacji

- Każdy automatyczny import wymaga BBOX i podglądu liczby obiektów.
- Limit jednego importu katalogowego wynosi domyślnie 20 000 obiektów; profil może mieć bezpieczniejszy limit źródłowy (GUGiK EGiB: 1000).
- Roczniki GSA są osobnymi wpisami; aplikacja nie zamienia ich automatycznie na nowsze.
- Status zewnętrznej usługi można sprawdzić ponownie, ale wynik kontroli jest zapisywany z datą.
- WMS jest źródłem obrazu mapy, nie geometrii wektorowej do analiz.
