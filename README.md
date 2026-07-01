# MongoDB projekat - Sistemi baza podataka

***Tema:***  Analiza preporuke i ocjena filmova po zanru, glumcima i reziserima

***Autor:***  Sofija Merćep  
***Indeks:***  IN57/2019  

---
#### Opis skupa podataka

Za potrebe projekta korišćena su dva povezana skupa podataka:

- [MovieLens 25M](https://grouplens.org/datasets/movielens/25m/)  
  Skup sadrži podatke o filmovima, korisničkim ocjenama, korisničkim tagovima i genome tagovima. U projektu su korišćene datoteke `movies.csv`, `ratings.csv`, `tags.csv`, `links.csv`, `genome-tags.csv` i `genome-scores.csv`. Najveća kolekcija je `ml_ratings`, koja sadrži 25.000.095 korisničkih ocjena.

- [The Movies Dataset / TMDB](https://www.kaggle.com/datasets/rounakbanik/the-movies-dataset)  
  Skup sadrži dodatne metapodatke o filmovima, kao što su budžet, prihod, popularnost, žanrovi, glumci, režiseri i ključne riječi. U projektu su korišćene datoteke `movies_metadata.csv`, `credits.csv` i `keywords.csv`.

Povezivanje MovieLens i TMDB podataka izvršeno je preko datoteke `links.csv`, odnosno preko veze:

```txt
ml_movies.movieId -> ml_links.movieId
ml_links.tmdbId  -> tmdb_movies_metadata.id
ml_links.tmdbId  -> tmdb_credits.id
ml_links.tmdbId  -> tmdb_keywords.id

## Rezultati

#### Šeme baze podataka

Za potrebe projekta kreirane su dvije šeme baze podataka, pri čemu je glavni cilj pri kreiranju druge šeme bio poboljšanje performansi složenih analitičkih upita nad velikom MongoDB bazom.

Inicijalna šema baze podataka, odnosno **v1 šema**, prati strukturu originalnih skupova podataka. Podaci su uvezeni u više odvojenih kolekcija, kao što su `ml_movies`, `ml_ratings`, `ml_links`, `ml_genome_scores`, `tmdb_movies_metadata`, `tmdb_credits` i `tmdb_keywords`. Ovakva šema je jednostavna za import i zadržava originalnu organizaciju podataka, ali je manje efikasna za analitiku jer upiti često zahtijevaju grupisanje velikog broja dokumenata i povezivanje više kolekcija pomoću `$lookup` operacija. Detalji implementacije upita nad inicijalnom šemom dostupni su u [v1/queries](./v1/queries), a rezultati u [v1/results](./v1/results).

Druga šema baze podataka, odnosno **v2 šema**, kreirana je transformacijom prve šeme, uz upotrebu denormalizacije, proračunatih vrijednosti, bucketizacije i indeksiranja. Centralna kolekcija druge šeme je `movies_optimized`, u kojoj jedan dokument predstavlja jedan film i sadrži podatke koji su u prvoj šemi bili raspoređeni kroz više kolekcija: osnovne identifikatore, žanrove, rating statistiku, komercijalne podatke, glumce, režisere, genome tagove i bucket polja. Za personalizovane preporuke kreirana je i kolekcija `user_profiles_optimized`, u kojoj je unaprijed pripremljen profil korisnika. Skripta za kreiranje optimizovane šeme nalazi se u [v2/build_movies_optimized.py](./v2/build_movies_optimized.py), detalji implementacije upita u [v2/queries](./v2/queries), a rezultati u [v2/results](./v2/results).

U drugoj šemi su podignuti indeksi nad poljima koja se najčešće koriste za filtriranje, sortiranje i pretragu, kao što su `movieId`, `tmdbId`, `releaseYear`, `genres`, `ratingStats.avgRating`, `ratingStats.ratingCount`, `commercial.profitStatus`, `people.topCastNames`, `people.directors`, `genome.highRelevanceTagNames` i bucket polja. Na taj način je omogućeno da MongoDB u optimizovanoj šemi pregleda znatno manji broj dokumenata pri izvršavanju istih upita.


#### Upiti

U projektu je implementirano 5 upita nad obje šeme baze podataka:

1. Koje Science Fiction filmove objavljene poslije 2000. godine mogu preporučiti široj publici ako imaju prosječnu MovieLens ocjenu veću od 4.0, najmanje 5.000 korisničkih ocjena, budžet veći od 50 miliona dolara i najmanje 3 glumca u cast listi?
2. Koji glumci iz prva 3 mjesta u cast listi se najčešće pojavljuju u filmovima koji imaju prosječnu MovieLens ocjenu veću od 4.0, najmanje 1.000 korisničkih ocjena i prihod veći od budžeta?
3. Koji filmovi imaju prosječnu MovieLens ocjenu veću od 4.1, najmanje 2.000 korisničkih ocjena, TMDB popularnost manju od 15, poznat budžet i prihod, ali budžet veći od prihoda?
4. Koji režiseri imaju najmanje 3 filma sa prosječnom MovieLens ocjenom većom od 4.0, najmanje 1.000 korisničkih ocjena po filmu i genome tagom dark, psychological, plot twist, twist, twist ending ili twists & turns, pri čemu je relevantnost taga veća od 0.7?
5. Koje filmove mogu preporučiti korisniku userId = 123, ako tražim filmove koje taj korisnik još nije ocijenio, a koji imaju prosječnu MovieLens ocjenu veću od 4.0, najmanje 1.000 ocjena, najmanje jedan zajednički žanr i najmanje jednog zajedničkog glumca iz prva 3 mjesta u cast listi ili istog režisera sa filmovima koje je korisnik ranije ocijenio ocjenom 4.5 ili 5.0?

Detalji implementacije upita nad prvom šemom dostupni su u [v1/queries](./v1/queries), a detalji implementacije upita nad drugom šemom u [v2/queries](./v2/queries).

### Performanse

Procjena performansi izvršena je poređenjem vremena izvršavanja upita nad v1 i v2 šemom, kao i pomoću metode explain("executionStats") koju nudi MongoDB.Na graficima je prikazano izmjereno vrijeme izvršavanja upita nad prvom i drugom verzijom baze, kao i broj pregledanih dokumenata po upitu.

![Vrijeme izvršavanja](./vrijeme_izvrsavanja.png?raw=true)
![Broj dokumenata](./pregledani_dokumenti_po_upitu.png?raw=true)