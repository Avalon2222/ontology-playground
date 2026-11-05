# Sumber data

Semua file di folder ini ditulis oleh `scripts/bangun_data.py`. Jangan sunting CSV-nya langsung; ubah skrip lalu
jalankan ulang (`python scripts/bangun_data.py`). Dengan seed bawaan (42) hasilnya selalu identik, dan tes
`tests/test_data.py` memastikan file yang di-commit sama dengan keluaran skrip.

## Data referensi (nyata)

| File | Isi | Sumber | Catatan |
|---|---|---|---|
| `provinsi.csv` | 38 provinsi: kode ISO 3166-2 (`ID-xx`), nama, alias umum, pulau/kawasan, ibu kota, koordinat ibu kota, penduduk (juta) | Kode ISO 3166-2:ID; penduduk pertengahan 2023 dari BPS, dibulatkan 0,1 juta; koordinat ibu kota dari peta umum | Empat provinsi pemekaran Papua 2022 disertakan; angka penduduk provinsi baru adalah perkiraan BPS |
| `pelabuhan.csv` (negara = Indonesia) | 30 pelabuhan: kode UN/LOCODE, nama, alias, kota, provinsi, operator, kelas, koordinat | UN/LOCODE (UNECE); daftar pelabuhan Pelindo per regional; informasi publik operator lain | Koordinat adalah perkiraan dermaga utama, bukan koordinat resmi. Kelas (utama internasional / utama / pengumpul) adalah penyederhanaan dari status pelabuhan, bukan klasifikasi resmi Kementerian Perhubungan |
| `pelabuhan.csv` (luar negeri) | 12 hub: Singapura, Port Klang, Shanghai, Qingdao, Mundra, Tokyo, Busan, Kaohsiung, Rotterdam, Manila, Ho Chi Minh City, Laem Chabang | UN/LOCODE | Dipilih karena lazim menjadi tujuan ekspor atau asal impor komoditas Indonesia |
| `komoditas.csv` | 21 komoditas: nama, alias, kategori, bab HS, moda angkut, arah perdagangan, satuan | Bab HS dari Harmonized System (WCO); moda angkut dari praktik umum pelayaran; arah dari pola neraca perdagangan Indonesia | Bauksit diberi arah "domestik" karena ekspor bijih mentah dilarang sejak 2023; "campuran" berarti ekspor dan impor sama-sama lazim |
| `komoditas_provinsi.csv` | Provinsi penghasil utama tiap komoditas, dengan peringkat | Ringkasan dari statistik produksi BPS, Kementerian ESDM, Kementerian Pertanian, dan KKP | Hanya provinsi penghasil terbesar (2–7 per komoditas); peringkat kasar, bukan angka produksi |
| `perusahaan.csv` (jenis = operator pelabuhan) | PT Pelabuhan Indonesia (Persero) dan Pelindo Regional 1–4, PT Pelabuhan Patimban Internasional, Badan Pengusahaan Batam, PT Krakatau Bandar Samudera | Informasi publik masing-masing lembaga | Struktur Pelindo pasca-merger 2021 disederhanakan menjadi induk + empat regional |

## Data sintetis

| File | Isi | Cara dibangkitkan |
|---|---|---|
| `perusahaan.csv` (lainnya) | 29 perusahaan fiktif: holding, pelayaran, tambang, perkebunan, energi, industri, manufaktur, perikanan, kehutanan, trader, tiga di antaranya asing | Ditulis tangan di skrip agar nama terasa wajar tetapi tidak menunjuk perusahaan nyata; struktur grup lewat kolom `induk_id` |
| `perusahaan_komoditas.csv` | Komoditas yang ditangani tiap perusahaan | Ditulis tangan, mengikuti sektor perusahaan |
| `kapal.csv` | 63 kapal: nama, jenis, bendera, DWT, panjang, tahun dibangun, pemilik | Jumlah armada per perusahaan ditentukan; jenis kapal mengikuti moda komoditas pemilik (curah kering → bulk carrier, curah cair → tanker, gas → LNG carrier, kontainer → kapal kontainer, break bulk → general cargo, ro-ro → ro-ro); DWT acak dalam rentang wajar per jenis; kapal milik perusahaan asing berbendera asing, kapal perusahaan Indonesia 92% berbendera Indonesia |
| `pelayaran.csv` | 520 pelayaran Januari 2024 – Desember 2026 | Komoditas dipilih dengan bobot mirip komposisi ekspor Indonesia (batu bara, CPO, nikel terbanyak); pelabuhan asal diambil dari provinsi penghasil komoditas itu; tujuan dari daftar pasar ekspor yang lazim per komoditas (batu bara → Tiongkok, India, Jepang, Korea; LNG → Jepang, Korea, Taiwan; dan seterusnya) atau hub domestik; durasi = jarak haversine × 1,25 ÷ kecepatan jenis kapal + 1–3 hari bongkar muat; **cabotage**: rute domestik hanya memakai kapal berbendera Indonesia; status (selesai/berlayar/dijadwalkan) dihitung terhadap tanggal potret 5 November 2026 |
| `insiden.csv` | 90 insiden di pelabuhan | Kapal dipilih dengan bobot umur (tahun sekarang − tahun dibangun) dan ×1,6 untuk bendera asing; lokasi dan tanggal diambil dari salah satu pelayaran kapal itu; jenis dan tingkat dari daftar tetap dengan probabilitas |

| `pelayaran_lengkap.csv` | Tampilan datar 520 pelayaran dengan nama kapal, pemilik, pelabuhan, negara, komoditas, dan pengirim (bukan id) | Hasil join dari tabel di atas, untuk analisis di luar aplikasi (pandas, chatbot); aplikasi sendiri tidak membacanya |

### Mengapa disintesis

Data AIS per pelayaran, manifes muatan, dan registri pemilik kapal yang lengkap tidak tersedia sebagai data terbuka,
dan menebak-nebak pelayaran perusahaan nyata akan menyesatkan. Generator membuat "dunia kecil" yang konsisten secara
internal sehingga ontologi, graf, dan mesin tanya-jawab bisa diuji dengan jawaban yang bisa diverifikasi. Fokus proyek
ini adalah **cara ontologi menghubungkan data**, bukan angkanya.

### Keterbatasan

- Rute hanya asal → tujuan, tanpa pelabuhan singgah.
- Satu pelayaran satu komoditas; kapal kontainer nyata membawa ratusan jenis barang.
- Tidak ada perubahan kepemilikan kapal, bendera, atau nama sepanjang waktu.
- Insiden tidak dibedakan antara kesalahan kapal dan kesalahan pelabuhan.
