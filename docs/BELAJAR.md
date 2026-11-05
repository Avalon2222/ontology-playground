# Belajar dari Ontology Playground

Panduan ini menjelaskan konsep di balik proyek, dari apa itu ontologi sampai cara pertanyaan berubah menjadi SQL.
Setiap bagian menunjuk ke file dan fungsi yang bisa kamu buka sambil membaca.

## 1. Apa itu ontologi (versi Palantir)

Dalam filsafat, ontologi adalah studi tentang "apa yang ada". Dalam Palantir Foundry, **ontology** adalah lapisan
perangkat lunak yang mendeskripsikan dunia sebuah organisasi sebagai *objek* dan *tautan*, lalu menempelkannya pada
data mentah:

| Konsep | Arti | Contoh di proyek ini |
|---|---|---|
| **Object type** | Jenis benda yang ada di dunia itu | Pelabuhan, Kapal, Komoditas, Perusahaan, Provinsi, Pelayaran, Insiden |
| **Property** | Atribut sebuah objek, dengan tipe | Kapal punya `dwt` (angka), `bendera` (kategori), `tahun_dibangun` (angka) |
| **Link type** | Relasi bernama antar dua tipe objek, dibaca dua arah | Kapal *dimiliki oleh* Perusahaan; Perusahaan *memiliki kapal* Kapal |
| **Backing dataset** | Tabel sumber yang "mendukung" tipe objek | tabel SQLite `kapal` dimuat dari `data/kapal.csv` |
| **Object set** | Himpunan objek hasil pencarian atau pivot | "semua Kapal yang dimiliki Perusahaan X" |
| **Search around** | Melompat dari satu himpunan ke himpunan lain lewat tautan | dari Pelabuhan → Pelayaran → Kapal → Perusahaan |
| **Action** | Perubahan terkendali pada objek, tercatat | "tandai kapal untuk pemeriksaan" |

Mengapa ini bernilai? Karena **semua aplikasi di atasnya tidak perlu tahu nama tabel**. Penjelajah objek, graf, pencarian,
dan tanya-jawab cukup membaca definisi ontologi. Menambah tipe objek baru berarti menambah definisi, bukan mengubah
setiap aplikasi.

## 2. Memodelkan ontologi dalam kode

Buka `src/ontologi.py`. Ada tiga dataclass:

```python
Properti(nama="dwt", label="Bobot mati (DWT)", tipe="angka", satuan="ton")

TipeObjek(id="kapal", label="Kapal", ikon="🚢", warna="#60a5fa", properti=(...),
          sinonim=("kapal", "vessel", "ship", "tanker"), kolom_alias="alias")

TipeTautan(id="kapal_dimiliki_oleh", label="dimiliki oleh", label_balik="memiliki kapal",
           sumber="kapal", tujuan="perusahaan",
           tabel="kapal", kolom_sumber="id", kolom_tujuan="pemilik_id", kardinalitas="N:1")
```

Kuncinya ada di `TipeTautan`: ia tidak hanya menyebut *makna* ("dimiliki oleh"), tetapi juga *di mana relasi itu
disimpan*. Ada dua pola:

- **N:1 dengan kolom penunjuk** (foreign key): tabelnya adalah tabel sumber sendiri, `kolom_sumber="id"`, `kolom_tujuan`
  adalah kolom penunjuk. Contoh: `kapal.pemilik_id`, `pelayaran.asal_id`.
- **N:N dengan tabel penghubung**: tabelnya tabel terpisah berisi dua kolom id. Contoh: `komoditas_provinsi`
  (`komoditas_id`, `provinsi_id`).

Karena keduanya dideskripsikan dengan tiga nama yang sama (`tabel`, `kolom_sumber`, `kolom_tujuan`), satu SQL generik
cukup untuk semua tautan:

```sql
SELECT t.* FROM {tujuan} t
JOIN {tabel} r ON r.{kolom_tujuan} = t.id
WHERE r.{kolom_sumber} = ?
```

Itulah isi `basis_data.tetangga()`. Fungsi itu dipakai object view (tab Objects), BFS graf, dan mesin tanya-jawab.

Catatan desain lain:

- `sinonim` adalah kata dalam pertanyaan yang menunjuk tipe ini ("kapal", "vessel"). Tes memastikan tidak ada sinonim
  yang dipakai dua tipe.
- `kata_kunci` pada tautan adalah kata yang membantu memilih tautan ketika dua tipe dihubungkan lebih dari satu tautan
  ("dari" → berangkat dari, "ke" → tiba di).
- Tautan ke tipe sendiri (`perusahaan_anak_dari`) dibaca dua arah: "anak usaha dari" dan "induk dari".

## 3. SQLite sebagai backing store

`src/basis_data.py` memuat setiap CSV ke SQLite **in-memory** dengan `pandas.DataFrame.to_sql`, membuat indeks pada
setiap kolom penunjuk, lalu menyalakan `PRAGMA query_only = 1` supaya koneksi tidak bisa menulis. Semua modul lain
memakai koneksi yang sama; di Streamlit koneksi itu dibungkus `st.cache_resource` supaya dibangun sekali per proses.

Mengapa SQLite dan bukan DuckDB atau Postgres? Karena bawaan Python, tanpa instalasi, dan SQL yang dihasilkan bisa
ditampilkan apa adanya ke pengguna. Untuk ribuan baris, kecepatannya lebih dari cukup.

`cek_integritas()` memeriksa bahwa setiap kolom penunjuk menunjuk id yang ada. Inilah "referential integrity" yang di
Foundry dijaga saat *object sync*. Di sini dijalankan di tab Data & Sources dan di tes.

## 4. Graf skema dan BFS

Ada dua graf yang mudah tertukar:

1. **Graf skema**: simpulnya *tipe objek*, sisinya *tipe tautan*. Hanya 7 simpul dan 15 sisi. Dipakai untuk mencari
   jalur antar tipe: dari Kapal ke Provinsi lewat apa? (`ontologi.jalur_terpendek`, BFS biasa dengan `collections.deque`.)
2. **Graf instans**: simpulnya *objek* (KPL-001, Balikpapan, ...), sisinya *tautan nyata*. Ribuan simpul. Dipakai tab
   Graph (`graf.subgraf`, BFS dari satu objek sampai kedalaman N, dengan batas simpul agar tidak meledak).

BFS (breadth-first search) menjelajah lapis demi lapis: semua tetangga jarak 1, lalu jarak 2, dan seterusnya. Karena
itu jalur pertama yang menemukan tujuan pasti yang terpendek.

```python
antrean = deque([[dari]])
dikunjungi = {dari}
while antrean:
    jalur = antrean.popleft()
    for lanjut in tetangga_tipe(jalur[-1]):
        if lanjut == ke:
            return jalur + [lanjut]
        if lanjut not in dikunjungi:
            dikunjungi.add(lanjut)
            antrean.append(jalur + [lanjut])
```

Untuk graf instans, `networkx.spring_layout` menata simpul: simpul yang terhubung saling tarik, yang tidak saling tolak.
Plotly menggambarnya sebagai satu trace per tipe tautan (garis) dan satu trace per tipe objek (titik), sehingga legenda
otomatis rapi dan klik simpul bisa ditangkap lewat `customdata`.

## 5. Dari pertanyaan ke SQL tanpa model bahasa

`src/kueri.py` adalah bagian paling menarik. Pertanyaan *"Kapal berbendera asing mana yang mengangkut nikel?"* diproses
begini:

1. **Entitas.** `indeks_entitas()` membangun daftar semua nama, alias, dan id objek, diurutkan dari yang terpanjang.
   Pencocokan dilakukan dengan regex berbatas kata, dan teks yang cocok dihapus supaya tidak dihitung dua kali.
   Hasil: `nikel` → Komoditas `nikel`.
2. **Tipe target.** Sisa teks dipindai dengan sinonim tipe objek. "kapal" → target Kapal. Kalau ada beberapa tipe, tipe
   yang diikuti kata tanya ("mana", "apa", "dengan") menjadi target.
3. **Maksud.** Ada "berapa"? → hitung. "terbanyak"? → peringkat. "terbesar", "tertua"? → urut properti. Tidak ada tipe
   tetapi ada entitas? → detail objek.
4. **Jalur.** BFS skema dari Kapal ke Komoditas: `kapal → pelayaran → komoditas` (dua lompatan). Kalau ada beberapa
   jalur dengan panjang sama, yang tautannya cocok dengan kata petunjuk atau melewati tipe yang disebut dalam pertanyaan
   mendapat skor lebih tinggi.
5. **Filter.** Nilai kategori yang muncul dalam teks dicocokkan ke properti kategori tipe yang ada di jalur ("asing" →
   `kapal.bendera <> 'Indonesia'`; "tanker" → `kapal.jenis = 'tanker'`; tahun empat digit → kolom tanggal/tahun).
6. **SQL.** `susun_sql()` menulis JOIN per langkah jalur. Untuk kolom penunjuk di tabel sumber: `JOIN b ON b.id = a.fk`;
   di tabel tujuan: `JOIN b ON b.fk = a.id`; tabel penghubung: dua JOIN; dua tautan sekaligus (asal atau tujuan):
   `b.id IN (a.asal_id, a.tujuan_id)`.

```sql
SELECT DISTINCT a0.*
FROM kapal a0
  JOIN pelayaran a1_1 ON a1_1.kapal_id = a0.id
  JOIN komoditas a1_2 ON a1_2.id = a1_1.komoditas_id
WHERE a1_2.id = ?
  AND a0.bendera <> ?
ORDER BY a0.nama
LIMIT 50
```

Tiga trik yang membuatnya terasa pintar padahal sederhana:

- **Penjelas vs target.** Pada "berapa insiden kapal Celebes Sentosa 8", kata "kapal" menempel pada entitas bertipe
  Kapal, jadi ia hanya penjelas; targetnya Insiden.
- **Pivot keberadaan.** Pada "kapal tertua yang pernah mengalami insiden tingkat tinggi", Insiden disebut tanpa nama.
  Mesin tetap menambahkannya ke jalur (tanpa `WHERE id = ?`) supaya filter `tingkat = tinggi` punya tempat.
- **Konteks.** Kalau pertanyaan tidak menyebut objek tetapi memuat "itu", "tersebut", "-nya", entitas dari pertanyaan
  sebelumnya dipakai lagi.

Batasnya juga jelas: mesin ini hanya memahami pola yang diprogramkan. Pertanyaan "mengapa" atau perbandingan dua
himpunan tidak bisa dijawab. Di situlah model bahasa berguna, bukan untuk menghitung, tetapi untuk menerjemahkan
pertanyaan bebas menjadi `Rencana` terstruktur yang sama. Proyek talk-to-the-data memakai pola itu.

## 6. Aksi dan jejak audit

Di Foundry, pengguna tidak mengubah tabel langsung. Mereka menjalankan **Action** yang punya definisi: objek apa yang
boleh menerimanya, parameter apa yang wajib, nilai apa yang sah. Setiap eksekusi tercatat (siapa, kapan, apa).
`src/aksi.py` meniru ini: `DefinisiAksi` + `jalankan()` yang memvalidasi lalu menambah `CatatanAudit`. Jejaknya disimpan
di `st.session_state`, bukan di basis data, supaya setiap pengunjung aplikasi punya ruang kerja sendiri dan basis data
tetap read-only.

## 7. Data sintetis yang jujur

Generator di `scripts/bangun_data.py` sengaja memisahkan data **nyata** (provinsi, pelabuhan, komoditas, operator) dari
data **sintetis** (perusahaan swasta, kapal, pelayaran, insiden). Yang sintetis tetap mengikuti aturan dunia nyata:
kapal curah mengangkut batu bara, bukan garmen; batu bara berangkat dari Kalimantan Timur, bukan Bali; rute domestik
hanya kapal berbendera Indonesia (cabotage). Dengan `random.Random(42)` hasilnya selalu sama, dan tes membandingkan
keluaran skrip dengan CSV yang di-commit. Kejujuran ini penting di README dan di aplikasi: pembaca harus tahu angka mana
yang bisa dikutip dan mana yang hanya ilustrasi.

## 8. Cara kode ini disusun

| Lapisan | File | Tanggung jawab |
|---|---|---|
| Skema | `src/ontologi.py` | definisi + navigasi skema |
| Penyimpanan | `src/basis_data.py` | SQLite, akses generik |
| Logika | `src/kueri.py`, `src/graf.py`, `src/aksi.py` | tanya-jawab, graf, aksi |
| UI | `app.py` | Streamlit, tanpa logika bisnis |
| Data | `scripts/bangun_data.py`, `data/` | generator + hasil |
| Uji | `tests/` | 79 tes, dijalankan CI |

Aturan yang dijaga: `app.py` tidak pernah menulis nama tabel; modul logika tidak pernah memanggil Streamlit. Dengan begitu
semua logika bisa diuji dengan `pytest` tanpa browser.
