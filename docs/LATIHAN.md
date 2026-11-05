# Latihan

Latihan bertingkat untuk memahami ontologi, graf, dan mesin tanya-jawab. Setiap latihan menyebut file yang perlu
disentuh dan cara memeriksa hasilnya. Jalankan `python -m pytest tests/ -q` setelah setiap perubahan.

## Tingkat 1: mengenal skema

**1.1 Alias baru.** Tambahkan alias "Priuk" untuk Tanjung Priok dan "Sulsel" sudah ada untuk Sulawesi Selatan; cek alias
mana yang belum ada untuk provinsi lain. Ubah di `scripts/bangun_data.py`, jalankan ulang, lalu uji di tab Ask dengan
"pelayaran ke Priuk". Mengapa alias ditulis di CSV dan bukan di `kueri.py`?

**1.2 Properti baru.** Tambahkan properti `tahun_operasi` pada Pelabuhan (tahun mulai beroperasi, boleh perkiraan untuk
beberapa pelabuhan). Tambahkan kolomnya di generator, lalu `Properti` di `src/ontologi.py`. Pastikan `tests/test_ontologi.py`
masih lolos (ia memeriksa setiap properti punya kolom).

**1.3 Baca SQL.** Di tab Ask, ajukan "komoditas apa yang berangkat dari Balikpapan" dan buka expander *Bagaimana jawaban ini
dihitung*. Tulis ulang SQL-nya dengan tangan di tab SQL dan pastikan hasilnya sama.

## Tingkat 2: tautan dan graf

**2.1 Tautan baru.** Tambahkan tautan Pelabuhan —*pelabuhan saudara*→ Pelabuhan (misalnya Tanjung Priok ↔ Patimban,
Belawan ↔ Kuala Tanjung) lewat tabel penghubung `pelabuhan_saudara.csv`. Daftarkan `TipeTautan` dengan `tabel`
penghubung dan lihat bahwa tab Objects, Graph, dan Ontology langsung menampilkannya tanpa perubahan di `app.py`.

**2.2 Derajat simpul.** Dengan `graf.graf_penuh(kon, {"kapal", "pelabuhan", "pelayaran"})`, hitung pelabuhan dengan
derajat tertinggi (`g.degree`). Bandingkan dengan jawaban tab Ask untuk "pelabuhan tersibuk". Mengapa bisa berbeda?
(Petunjuk: pelayaran yang sama bisa dihitung sekali atau dua kali.)

**2.3 Jalur alternatif.** `ontologi.jalur_terpendek("kapal", "provinsi")` mengembalikan jalur lewat Perusahaan (kantor
pusat), bukan lewat Pelabuhan. Ubah skor di `kueri.pilih_jalur` supaya pertanyaan "kapal di Kalimantan Timur" memilih
jalur lewat pelayaran. Apa dampaknya pada "perusahaan di Kalimantan Timur"? Tambahkan tes untuk keduanya.

## Tingkat 3: mesin tanya-jawab

**3.1 Filter bulan.** Mesin baru mengenali tahun. Tambahkan pengenalan bulan ("Maret 2025", "bulan lalu") di
`kueri.kenali_filter` dengan operator baru, lalu `_syarat_filter` yang memakai `substr(kolom, 1, 7)`.

**3.2 Agregat selain jumlah.** "total muatan batu bara ke Tiongkok" seharusnya menjumlahkan `muatan`, bukan menghitung
baris. Tambahkan maksud `jumlahkan` dengan kata kunci "total", "berapa ton", dan kolom angka yang dipilih dari
`SUPERLATIF_PROPERTI` atau daftar baru.

**3.3 Negasi.** "kapal yang belum pernah mengalami insiden" membutuhkan `LEFT JOIN ... WHERE insiden.id IS NULL` atau
`NOT EXISTS`. Rancang cara menandai pivot keberadaan sebagai negatif (`Entitas` dengan atribut baru) dan susun SQL-nya.

**3.4 Pertanyaan dua himpunan.** "pelabuhan yang disinggahi kapal Meridian tetapi tidak oleh kapal Pacific Ore".
Pikirkan dulu apakah ini masih bisa dilakukan dengan satu `Rencana`, atau perlu dua himpunan objek dan operasi
himpunan (selisih). Tulis desainnya sebelum kode.

## Tingkat 4: tipe objek baru

**4.1 Smelter.** Tambahkan tipe objek *Smelter* (nama, provinsi, komoditas yang diolah, kapasitas) dengan tautan
Smelter —terletak di→ Provinsi dan Smelter —mengolah→ Komoditas. Cukup tiga tempat: generator, `src/ontologi.py`,
dan satu tes. Lalu coba "smelter di Sulawesi Tengah" dan "komoditas yang diolah smelter di Maluku Utara".

**4.2 Posisi dari AIS.** Rancang tipe objek *Posisi* (kapal, waktu, lat, lon, kecepatan) yang jumlahnya bisa puluhan
ribu baris. Apa yang harus berubah di `graf.subgraf` supaya graf tidak meledak? Apa yang harus berubah di indeks entitas
`kueri.indeks_entitas` supaya tidak lambat?

## Tingkat 5: aksi yang menulis

**5.1 SQLite di disk.** Saat ini aksi hanya mencatat di sesi. Ubah `aksi.jalankan` supaya aksi `tandai_pemeriksaan`
juga menulis ke tabel `daftar_pantau` di file SQLite terpisah (bukan basis data ontologi yang read-only). Pikirkan:
apa yang terjadi bila dua pengunjung menandai kapal yang sama?

**5.2 Undo.** Tambahkan aksi `batalkan_tanda` yang hanya sah bila ada tanda sebelumnya pada kapal itu. Validasinya harus
membaca jejak audit, bukan hanya parameter.

## Pertanyaan refleksi

- Apa yang hilang kalau skema ontologi dibuang dan `app.py` langsung menulis SQL untuk tiap fitur?
- Mesin tanya-jawab ini deterministik: jawaban yang sama untuk pertanyaan yang sama, dan setiap langkah bisa dilihat.
  Apa yang kamu korbankan kalau menggantinya dengan model bahasa yang langsung menulis SQL? Apa jalan tengahnya?
- Data sintetis memudahkan pengujian. Kapan data sintetis justru menyesatkan pembaca, dan bagaimana README proyek ini
  mencegahnya?
