"""
bangun_data.py - Membangun ulang semua file di data/ untuk Ontology Playground.

    python scripts/bangun_data.py            # tulis ulang data/*.csv dengan seed tetap (hasil selalu sama)
    python scripts/bangun_data.py --seed 7   # variasi lain

Dua jenis data dihasilkan dari sini:

1. Data referensi yang NYATA dan ditulis langsung di file ini: 38 provinsi, 30 pelabuhan Indonesia dan
   12 pelabuhan luar negeri, 21 komoditas beserta bab HS, dan peta komoditas -> provinsi penghasil.
   Operator pelabuhan (Pelindo dan regionalnya, BP Batam, Pelabuhan Patimban, Krakatau Bandar Samudera)
   juga nyata dan bersumber dari informasi publik.
2. Data operasional yang DISINTESIS: perusahaan swasta (nama fiktif), kapal, pelayaran, dan insiden.
   Angkanya realistis (bobot mati, durasi dari jarak haversine, pola rute per komoditas, aturan cabotage),
   tetapi tidak menggambarkan kapal atau perusahaan yang sungguh ada. Lihat data/SUMBER_DATA.md.

Semua ditulis sebagai CSV sederhana supaya mudah dibaca, di-diff, dan dimuat ke SQLite oleh src/basis_data.py.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_DATA = ROOT / "data"
HARI_INI = date(2026, 11, 5)   # tanggal potret, supaya status pelayaran deterministik

# ---------------------------------------------------------------------------
# 1. PROVINSI (38, BPS; penduduk pertengahan 2023 dibulatkan 0,1 juta; lat/lon = ibu kota)
# ---------------------------------------------------------------------------
PROVINSI = [
    # id, nama, alias, pulau, ibu_kota, lat, lon, penduduk_juta
    ("ID-AC", "Aceh", "NAD|Nanggroe Aceh Darussalam", "Sumatra", "Banda Aceh", 5.55, 95.32, 5.5),
    ("ID-SU", "Sumatera Utara", "Sumut", "Sumatra", "Medan", 3.59, 98.67, 15.4),
    ("ID-SB", "Sumatera Barat", "Sumbar", "Sumatra", "Padang", -0.95, 100.35, 5.8),
    ("ID-RI", "Riau", "", "Sumatra", "Pekanbaru", 0.51, 101.45, 6.7),
    ("ID-JA", "Jambi", "", "Sumatra", "Jambi", -1.61, 103.61, 3.7),
    ("ID-SS", "Sumatera Selatan", "Sumsel", "Sumatra", "Palembang", -2.99, 104.76, 8.8),
    ("ID-BE", "Bengkulu", "", "Sumatra", "Bengkulu", -3.80, 102.26, 2.1),
    ("ID-LA", "Lampung", "", "Sumatra", "Bandar Lampung", -5.43, 105.26, 9.2),
    ("ID-BB", "Kepulauan Bangka Belitung", "Babel|Bangka Belitung", "Sumatra", "Pangkalpinang", -2.13, 106.11, 1.5),
    ("ID-KR", "Kepulauan Riau", "Kepri", "Sumatra", "Tanjung Pinang", 0.92, 104.45, 2.2),
    ("ID-JK", "DKI Jakarta", "Jakarta", "Jawa", "Jakarta", -6.21, 106.85, 10.7),
    ("ID-JB", "Jawa Barat", "Jabar", "Jawa", "Bandung", -6.91, 107.61, 49.9),
    ("ID-JT", "Jawa Tengah", "Jateng", "Jawa", "Semarang", -6.99, 110.42, 37.5),
    ("ID-YO", "DI Yogyakarta", "Yogyakarta|Jogja|DIY", "Jawa", "Yogyakarta", -7.80, 110.36, 3.7),
    ("ID-JI", "Jawa Timur", "Jatim", "Jawa", "Surabaya", -7.25, 112.75, 41.5),
    ("ID-BT", "Banten", "", "Jawa", "Serang", -6.12, 106.15, 12.3),
    ("ID-BA", "Bali", "", "Bali & Nusa Tenggara", "Denpasar", -8.65, 115.22, 4.4),
    ("ID-NB", "Nusa Tenggara Barat", "NTB", "Bali & Nusa Tenggara", "Mataram", -8.58, 116.12, 5.6),
    ("ID-NT", "Nusa Tenggara Timur", "NTT", "Bali & Nusa Tenggara", "Kupang", -10.18, 123.60, 5.6),
    ("ID-KB", "Kalimantan Barat", "Kalbar", "Kalimantan", "Pontianak", -0.03, 109.34, 5.5),
    ("ID-KT", "Kalimantan Tengah", "Kalteng", "Kalimantan", "Palangka Raya", -2.21, 113.92, 2.8),
    ("ID-KS", "Kalimantan Selatan", "Kalsel", "Kalimantan", "Banjarbaru", -3.44, 114.83, 4.2),
    ("ID-KI", "Kalimantan Timur", "Kaltim", "Kalimantan", "Samarinda", -0.50, 117.15, 4.0),
    ("ID-KU", "Kalimantan Utara", "Kaltara", "Kalimantan", "Tanjung Selor", 2.84, 117.37, 0.7),
    ("ID-SA", "Sulawesi Utara", "Sulut", "Sulawesi", "Manado", 1.49, 124.84, 2.6),
    ("ID-ST", "Sulawesi Tengah", "Sulteng", "Sulawesi", "Palu", -0.90, 119.87, 3.1),
    ("ID-SN", "Sulawesi Selatan", "Sulsel", "Sulawesi", "Makassar", -5.14, 119.42, 9.4),
    ("ID-SG", "Sulawesi Tenggara", "Sultra", "Sulawesi", "Kendari", -3.97, 122.51, 2.8),
    ("ID-GO", "Gorontalo", "", "Sulawesi", "Gorontalo", 0.54, 123.06, 1.2),
    ("ID-SR", "Sulawesi Barat", "Sulbar", "Sulawesi", "Mamuju", -2.67, 118.89, 1.5),
    ("ID-MA", "Maluku", "", "Maluku", "Ambon", -3.70, 128.18, 1.9),
    ("ID-MU", "Maluku Utara", "Malut", "Maluku", "Sofifi", 0.73, 127.57, 1.3),
    ("ID-PA", "Papua", "", "Papua", "Jayapura", -2.53, 140.72, 1.1),
    ("ID-PB", "Papua Barat", "", "Papua", "Manokwari", -0.86, 134.06, 0.6),
    ("ID-PD", "Papua Barat Daya", "", "Papua", "Sorong", -0.88, 131.26, 0.6),
    ("ID-PT", "Papua Tengah", "", "Papua", "Nabire", -3.37, 135.50, 1.4),
    ("ID-PE", "Papua Pegunungan", "", "Papua", "Wamena", -4.10, 138.95, 1.5),
    ("ID-PS", "Papua Selatan", "", "Papua", "Merauke", -8.49, 140.40, 0.5),
]

# ---------------------------------------------------------------------------
# 2. PERUSAHAAN
#    Operator pelabuhan = entitas nyata (informasi publik). Sisanya FIKTIF, nama disusun agar terasa
#    wajar tetapi tidak menunjuk perusahaan yang ada. Kolom negara/provinsi_id untuk kantor pusat.
# ---------------------------------------------------------------------------
PERUSAHAAN = [
    # id, nama, jenis, kepemilikan, negara, provinsi_id, induk_id, tahun_berdiri, deskripsi
    ("pelindo", "PT Pelabuhan Indonesia (Persero)", "operator pelabuhan", "BUMN", "Indonesia", "ID-JK", "", 1992,
     "BUMN operator pelabuhan hasil merger Pelindo I-IV pada 2021; mengelola sebagian besar pelabuhan komersial."),
    ("pelindo_r1", "Pelindo Regional 1", "operator pelabuhan", "BUMN", "Indonesia", "ID-SU", "pelindo", 2021,
     "Unit regional Pelindo untuk Sumatra bagian utara (eks Pelindo I)."),
    ("pelindo_r2", "Pelindo Regional 2", "operator pelabuhan", "BUMN", "Indonesia", "ID-JK", "pelindo", 2021,
     "Unit regional Pelindo untuk Jakarta, Sumatra bagian selatan, dan Kalimantan Barat (eks Pelindo II)."),
    ("pelindo_r3", "Pelindo Regional 3", "operator pelabuhan", "BUMN", "Indonesia", "ID-JI", "pelindo", 2021,
     "Unit regional Pelindo untuk Jawa Tengah, Jawa Timur, Bali, Nusa Tenggara, Kalimantan Selatan (eks Pelindo III)."),
    ("pelindo_r4", "Pelindo Regional 4", "operator pelabuhan", "BUMN", "Indonesia", "ID-SN", "pelindo", 2021,
     "Unit regional Pelindo untuk Kalimantan Timur, Sulawesi, Maluku, Papua (eks Pelindo IV)."),
    ("ppi", "PT Pelabuhan Patimban Internasional", "operator pelabuhan", "patungan", "Indonesia", "ID-JB", "", 2021,
     "Operator terminal Pelabuhan Patimban, pelabuhan baru untuk ekspor kendaraan dari Jawa Barat."),
    ("bp_batam", "Badan Pengusahaan Batam", "operator pelabuhan", "pemerintah", "Indonesia", "ID-KR", "", 1971,
     "Pengelola kawasan perdagangan bebas Batam termasuk Pelabuhan Batu Ampar."),
    ("kbs", "PT Krakatau Bandar Samudera", "operator pelabuhan", "BUMN", "Indonesia", "ID-BT", "", 1996,
     "Operator Pelabuhan Cigading di Cilegon, pelabuhan curah terbesar untuk bahan baku baja dan pangan."),
    # --- fiktif ---
    ("grp_khatulistiwa", "Khatulistiwa Group", "holding", "swasta", "Indonesia", "ID-JK", "", 1998,
     "Holding fiktif yang membawahi perusahaan pelayaran dan tambang bauksit."),
    ("pt_skl", "PT Samudra Khatulistiwa Lines", "pelayaran", "swasta", "Indonesia", "ID-JK", "grp_khatulistiwa", 2003,
     "Perusahaan pelayaran kontainer domestik dan intra-Asia (fiktif)."),
    ("pt_bauksit", "PT Bauksit Khatulistiwa", "tambang", "swasta", "Indonesia", "ID-KB", "grp_khatulistiwa", 2008,
     "Penambang bauksit di Kalimantan Barat yang memasok smelter domestik (fiktif)."),
    ("nmh", "Nusantara Maritim Holding", "holding", "swasta", "Indonesia", "ID-JI", "", 1990,
     "Holding fiktif berbasis Surabaya untuk armada curah dan kontainer."),
    ("pt_nbc", "PT Nusantara Bulk Carriers", "pelayaran", "swasta", "Indonesia", "ID-JI", "nmh", 1995,
     "Operator kapal curah kering untuk batu bara, nikel, semen, dan pupuk (fiktif)."),
    ("pt_kei", "PT Kontainer Ekspres Indonesia", "pelayaran", "swasta", "Indonesia", "ID-JK", "nmh", 2007,
     "Pelayaran kontainer dan ro-ro untuk garmen, elektronik, kendaraan (fiktif)."),
    ("pt_borneo", "PT Borneo Energi Tambang", "tambang", "swasta", "Indonesia", "ID-KI", "", 2001,
     "Produsen batu bara termal di Kalimantan Timur (fiktif)."),
    ("pt_mahakam_log", "PT Mahakam Logistik Maritim", "pelayaran", "swasta", "Indonesia", "ID-KI", "pt_borneo", 2012,
     "Anak usaha logistik laut PT Borneo Energi Tambang; tongkang dan kapal curah (fiktif)."),
    ("pt_sawit", "PT Sawit Andalas Makmur", "perkebunan", "swasta", "Indonesia", "ID-RI", "", 1999,
     "Perkebunan dan pabrik kelapa sawit di Riau dan Sumatera Utara (fiktif)."),
    ("pt_andalas_tankers", "PT Andalas Tankers", "pelayaran", "swasta", "Indonesia", "ID-RI", "pt_sawit", 2010,
     "Armada tanker CPO milik grup Sawit Andalas (fiktif)."),
    ("pt_nikel", "PT Nikel Celebes Mandiri", "tambang", "patungan", "Indonesia", "ID-ST", "", 2015,
     "Penambang dan pengolah nikel di Morowali dan Konawe (fiktif)."),
    ("pt_gas", "PT Gas Mahakam Energi", "energi", "swasta", "Indonesia", "ID-KI", "", 2005,
     "Produsen gas dan minyak di Kalimantan Timur dengan ekspor LNG (fiktif)."),
    ("pt_pupuk_nusa", "PT Pupuk Nusa Raya", "industri", "BUMN", "Indonesia", "ID-JI", "", 1979,
     "Produsen pupuk urea dan NPK di Gresik dan Bontang (fiktif)."),
    ("pt_semen_jawa", "PT Semen Jawa Persada", "industri", "swasta", "Indonesia", "ID-JB", "", 1985,
     "Produsen semen yang mendistribusikan lewat laut ke Indonesia timur (fiktif)."),
    ("pt_perikanan", "PT Perikanan Timur Nusantara", "perikanan", "swasta", "Indonesia", "ID-SA", "", 2011,
     "Pengolah dan pengekspor tuna dan udang beku dari Bitung dan Ambon (fiktif)."),
    ("pt_kayu", "PT Kayu Kalimantan Lestari", "kehutanan", "swasta", "Indonesia", "ID-KB", "", 1992,
     "Produsen kayu olahan dan pulp (fiktif)."),
    ("pt_tembaga", "PT Tembaga Papua Mining", "tambang", "patungan", "Indonesia", "ID-PT", "", 2004,
     "Penambang konsentrat tembaga di Papua Tengah (fiktif)."),
    ("pt_tanker_bumi", "PT Tanker Bumi Persada", "pelayaran", "swasta", "Indonesia", "ID-JK", "", 2000,
     "Operator tanker produk minyak dan minyak mentah untuk pasar domestik (fiktif)."),
    ("pt_karet", "PT Karet Sriwijaya", "perkebunan", "swasta", "Indonesia", "ID-SS", "", 1988,
     "Perkebunan karet dan kopi di Sumatera Selatan (fiktif)."),
    ("pt_kakao", "PT Kakao Celebes", "perkebunan", "swasta", "Indonesia", "ID-SN", "", 2009,
     "Pengumpul dan pengekspor biji kakao Sulawesi (fiktif)."),
    ("pt_baja", "PT Baja Cilegon Mandiri", "industri", "swasta", "Indonesia", "ID-BT", "", 1996,
     "Pabrik baja di Cilegon yang mengirim produk ke Jawa Timur dan Kalimantan (fiktif)."),
    ("pt_logistik_kep", "PT Logistik Kepulauan Maluku", "pelayaran", "swasta", "Indonesia", "ID-MA", "", 2014,
     "Pelayaran rakyat skala menengah untuk beras, semen, dan ikan antar pulau di timur (fiktif)."),
    ("pt_garmen", "PT Garmen Pantura Ekspor", "manufaktur", "swasta", "Indonesia", "ID-JT", "", 2002,
     "Produsen garmen untuk merek internasional, pabrik di Jawa Tengah (fiktif)."),
    ("pt_elektronik", "PT Elektronik Batam Komponen", "manufaktur", "asing", "Indonesia", "ID-KR", "", 2006,
     "Perakit komponen elektronik di kawasan bebas Batam (fiktif)."),
    ("pt_otomotif", "PT Otomotif Karawang Ekspor", "manufaktur", "patungan", "Indonesia", "ID-JB", "", 1997,
     "Pabrik perakitan kendaraan yang mengekspor lewat Patimban dan Tanjung Priok (fiktif)."),
    ("pt_pangan", "PT Pangan Nusantara Trading", "trader", "swasta", "Indonesia", "ID-JK", "", 2001,
     "Importir beras dan gula serta distributor antar pulau (fiktif)."),
    ("meridian", "Meridian Shipping Pte Ltd", "pelayaran", "asing", "Singapura", "", "", 2004,
     "Operator kapal curah dan tanker berbendera asing yang melayani ekspor Indonesia (fiktif)."),
    ("pacific_ore", "Pacific Ore Carriers Ltd", "pelayaran", "asing", "Hong Kong", "", "", 2009,
     "Pengangkut bijih mineral ke smelter di Tiongkok (fiktif)."),
    ("oriental_gas", "Oriental Gas Transport Co.", "pelayaran", "asing", "Jepang", "", "", 1988,
     "Operator kapal LNG untuk pembeli di Asia Timur (fiktif)."),
]

# Nama pendek yang lazim dipakai orang saat bertanya (kolom alias, dipisah |)
ALIAS_PERUSAHAAN = {
    "pelindo": "Pelindo", "pelindo_r1": "Pelindo 1|Pelindo I", "pelindo_r2": "Pelindo 2|Pelindo II",
    "pelindo_r3": "Pelindo 3|Pelindo III", "pelindo_r4": "Pelindo 4|Pelindo IV", "ppi": "Patimban Internasional|PPI",
    "bp_batam": "BP Batam", "kbs": "KBS|Krakatau Bandar Samudera", "grp_khatulistiwa": "Khatulistiwa",
    "pt_skl": "Samudra Khatulistiwa|SKL", "pt_bauksit": "Bauksit Khatulistiwa", "nmh": "Nusantara Maritim|NMH",
    "pt_nbc": "Nusantara Bulk|NBC", "pt_kei": "Kontainer Ekspres|KEI", "pt_borneo": "Borneo Energi",
    "pt_mahakam_log": "Mahakam Logistik", "pt_sawit": "Sawit Andalas", "pt_andalas_tankers": "Andalas Tankers",
    "pt_nikel": "Nikel Celebes", "pt_gas": "Gas Mahakam", "pt_pupuk_nusa": "Pupuk Nusa", "pt_semen_jawa": "Semen Jawa",
    "pt_perikanan": "Perikanan Timur", "pt_kayu": "Kayu Kalimantan", "pt_tembaga": "Tembaga Papua",
    "pt_tanker_bumi": "Tanker Bumi", "pt_karet": "Karet Sriwijaya", "pt_kakao": "Kakao Celebes", "pt_baja": "Baja Cilegon",
    "pt_logistik_kep": "Logistik Kepulauan", "pt_garmen": "Garmen Pantura", "pt_elektronik": "Elektronik Batam",
    "pt_otomotif": "Otomotif Karawang", "pt_pangan": "Pangan Nusantara", "meridian": "Meridian",
    "pacific_ore": "Pacific Ore", "oriental_gas": "Oriental Gas",
}

# Komoditas yang ditangani tiap perusahaan (link N:N perusahaan -> komoditas)
PERUSAHAAN_KOMODITAS = {
    "pt_skl": ["garmen", "elektronik", "ikan", "kopi", "karet"],
    "pt_bauksit": ["bauksit"],
    "pt_nbc": ["batu_bara", "nikel", "semen", "pupuk", "bauksit"],
    "pt_kei": ["garmen", "elektronik", "kendaraan", "beras", "kakao"],
    "pt_borneo": ["batu_bara"],
    "pt_mahakam_log": ["batu_bara", "kayu"],
    "pt_sawit": ["cpo"],
    "pt_andalas_tankers": ["cpo", "bbm"],
    "pt_nikel": ["nikel"],
    "pt_gas": ["lng", "minyak_mentah"],
    "pt_pupuk_nusa": ["pupuk"],
    "pt_semen_jawa": ["semen"],
    "pt_perikanan": ["ikan"],
    "pt_kayu": ["kayu"],
    "pt_tembaga": ["tembaga"],
    "pt_tanker_bumi": ["bbm", "minyak_mentah", "cpo"],
    "pt_karet": ["karet", "kopi"],
    "pt_kakao": ["kakao"],
    "pt_baja": ["baja"],
    "pt_logistik_kep": ["beras", "semen", "ikan", "baja"],
    "pt_garmen": ["garmen"],
    "pt_elektronik": ["elektronik"],
    "pt_otomotif": ["kendaraan"],
    "pt_pangan": ["beras", "gula"],
    "meridian": ["batu_bara", "nikel", "cpo", "minyak_mentah"],
    "pacific_ore": ["nikel", "tembaga", "bauksit"],
    "oriental_gas": ["lng"],
}

# ---------------------------------------------------------------------------
# 3. PELABUHAN (id = UN/LOCODE; koordinat perkiraan dermaga utama)
# ---------------------------------------------------------------------------
PELABUHAN = [
    # id, nama, alias, kota, negara, provinsi_id, operator_id, kelas, lat, lon
    ("IDJKT", "Tanjung Priok", "Priok", "Jakarta Utara", "Indonesia", "ID-JK", "pelindo_r2", "utama internasional", -6.104, 106.883),
    ("IDSUB", "Tanjung Perak", "Perak|Surabaya", "Surabaya", "Indonesia", "ID-JI", "pelindo_r3", "utama internasional", -7.200, 112.733),
    ("IDBLW", "Belawan", "Medan", "Medan", "Indonesia", "ID-SU", "pelindo_r1", "utama internasional", 3.783, 98.683),
    ("IDMAK", "Makassar", "Soekarno-Hatta Makassar", "Makassar", "Indonesia", "ID-SN", "pelindo_r4", "utama internasional", -5.117, 119.400),
    ("IDSRG", "Tanjung Emas", "Emas|Semarang", "Semarang", "Indonesia", "ID-JT", "pelindo_r3", "utama", -6.950, 110.417),
    ("IDBPN", "Balikpapan", "Semayang", "Balikpapan", "Indonesia", "ID-KI", "pelindo_r4", "utama", -1.267, 116.817),
    ("IDSRI", "Samarinda", "Palaran", "Samarinda", "Indonesia", "ID-KI", "pelindo_r4", "pengumpul", -0.500, 117.150),
    ("IDDUM", "Dumai", "", "Dumai", "Indonesia", "ID-RI", "pelindo_r1", "utama", 1.683, 101.450),
    ("IDBDJ", "Banjarmasin", "Trisakti", "Banjarmasin", "Indonesia", "ID-KS", "pelindo_r3", "utama", -3.317, 114.583),
    ("IDBIT", "Bitung", "", "Bitung", "Indonesia", "ID-SA", "pelindo_r4", "utama internasional", 1.433, 125.183),
    ("IDSOQ", "Sorong", "", "Sorong", "Indonesia", "ID-PD", "pelindo_r4", "utama", -0.883, 131.250),
    ("IDPTB", "Patimban", "", "Subang", "Indonesia", "ID-JB", "ppi", "utama internasional", -6.233, 107.883),
    ("IDKTJ", "Kuala Tanjung", "", "Batu Bara", "Indonesia", "ID-SU", "pelindo_r1", "utama internasional", 3.367, 99.450),
    ("IDPNJ", "Panjang", "", "Bandar Lampung", "Indonesia", "ID-LA", "pelindo_r2", "utama", -5.467, 105.317),
    ("IDTBY", "Teluk Bayur", "Padang", "Padang", "Indonesia", "ID-SB", "pelindo_r2", "utama", -1.000, 100.367),
    ("IDPNK", "Pontianak", "Dwikora", "Pontianak", "Indonesia", "ID-KB", "pelindo_r2", "pengumpul", -0.017, 109.333),
    ("IDAMQ", "Ambon", "Yos Sudarso Ambon", "Ambon", "Indonesia", "ID-MA", "pelindo_r4", "pengumpul", -3.700, 128.183),
    ("IDDJJ", "Jayapura", "", "Jayapura", "Indonesia", "ID-PA", "pelindo_r4", "pengumpul", -2.533, 140.717),
    ("IDBOA", "Benoa", "Denpasar", "Denpasar", "Indonesia", "ID-BA", "pelindo_r3", "pengumpul", -8.750, 115.217),
    ("IDBTM", "Batu Ampar", "Batam", "Batam", "Indonesia", "ID-KR", "bp_batam", "utama internasional", 1.167, 104.000),
    ("IDPLM", "Palembang", "Boom Baru", "Palembang", "Indonesia", "ID-SS", "pelindo_r2", "utama", -2.967, 104.767),
    ("IDKDI", "Kendari", "Bungkutoko", "Kendari", "Indonesia", "ID-SG", "pelindo_r4", "pengumpul", -3.967, 122.583),
    ("IDTRK", "Tarakan", "", "Tarakan", "Indonesia", "ID-KU", "pelindo_r4", "pengumpul", 3.300, 117.600),
    ("IDMKQ", "Merauke", "", "Merauke", "Indonesia", "ID-PS", "pelindo_r4", "pengumpul", -8.483, 140.400),
    ("IDKUP", "Tenau Kupang", "Kupang", "Kupang", "Indonesia", "ID-NT", "pelindo_r3", "pengumpul", -10.200, 123.533),
    ("IDLEM", "Lembar", "Lombok", "Lombok Barat", "Indonesia", "ID-NB", "pelindo_r3", "pengumpul", -8.733, 116.067),
    ("IDTTE", "Ternate", "Ahmad Yani Ternate", "Ternate", "Indonesia", "ID-MU", "pelindo_r4", "pengumpul", 0.783, 127.383),
    ("IDMKW", "Manokwari", "", "Manokwari", "Indonesia", "ID-PB", "pelindo_r4", "pengumpul", -0.867, 134.083),
    ("IDCIG", "Cigading", "Cilegon", "Cilegon", "Indonesia", "ID-BT", "kbs", "utama", -5.933, 106.017),
    ("IDGRE", "Gresik", "", "Gresik", "Indonesia", "ID-JI", "pelindo_r3", "utama", -7.150, 112.650),
    # luar negeri (tujuan ekspor / asal impor), tanpa provinsi dan operator
    ("SGSIN", "Singapura", "Singapore", "Singapura", "Singapura", "", "", "hub internasional", 1.264, 103.840),
    ("MYPKG", "Port Klang", "Klang", "Klang", "Malaysia", "", "", "hub internasional", 3.000, 101.400),
    ("CNSHA", "Shanghai", "", "Shanghai", "Tiongkok", "", "", "hub internasional", 31.230, 121.490),
    ("CNTAO", "Qingdao", "", "Qingdao", "Tiongkok", "", "", "hub internasional", 36.067, 120.383),
    ("INMUN", "Mundra", "", "Mundra", "India", "", "", "hub internasional", 22.750, 69.700),
    ("JPTYO", "Tokyo", "", "Tokyo", "Jepang", "", "", "hub internasional", 35.650, 139.767),
    ("KRPUS", "Busan", "", "Busan", "Korea Selatan", "", "", "hub internasional", 35.100, 129.033),
    ("TWKHH", "Kaohsiung", "", "Kaohsiung", "Taiwan", "", "", "hub internasional", 22.617, 120.283),
    ("NLRTM", "Rotterdam", "", "Rotterdam", "Belanda", "", "", "hub internasional", 51.950, 4.133),
    ("PHMNL", "Manila", "", "Manila", "Filipina", "", "", "hub internasional", 14.583, 120.967),
    ("VNSGN", "Ho Chi Minh City", "Saigon", "Ho Chi Minh City", "Vietnam", "", "", "hub internasional", 10.767, 106.700),
    ("THLCH", "Laem Chabang", "", "Chonburi", "Thailand", "", "", "hub internasional", 13.083, 100.883),
]

# ---------------------------------------------------------------------------
# 4. KOMODITAS (bab HS = 2 digit pertama kode Harmonized System)
#    moda menentukan jenis kapal; arah menentukan pola rute pada generator.
# ---------------------------------------------------------------------------
KOMODITAS = [
    # id, nama, alias, kategori, hs_bab, moda, arah, satuan
    ("batu_bara", "Batu bara", "coal|batubara", "energi", "27", "curah kering", "ekspor", "ton"),
    ("cpo", "Minyak kelapa sawit (CPO)", "sawit|palm oil|kelapa sawit", "perkebunan", "15", "curah cair", "ekspor", "ton"),
    ("nikel", "Bijih nikel dan feronikel", "nickel|feronikel", "mineral", "26", "curah kering", "ekspor", "ton"),
    ("lng", "Gas alam cair (LNG)", "gas alam|gas", "energi", "27", "gas", "ekspor", "ton"),
    ("minyak_mentah", "Minyak mentah", "crude|minyak bumi", "energi", "27", "curah cair", "campuran", "ton"),
    ("bbm", "Bahan bakar minyak (BBM)", "solar|bensin|bahan bakar", "energi", "27", "curah cair", "impor", "ton"),
    ("pupuk", "Pupuk", "urea|fertilizer", "industri", "31", "curah kering", "domestik", "ton"),
    ("semen", "Semen", "cement", "industri", "25", "curah kering", "domestik", "ton"),
    ("beras", "Beras", "rice|padi", "pangan", "10", "curah kering", "impor", "ton"),
    ("gula", "Gula", "sugar|gula pasir", "pangan", "17", "curah kering", "impor", "ton"),
    ("bauksit", "Bauksit", "bauxite|alumina", "mineral", "26", "curah kering", "domestik", "ton"),
    ("karet", "Karet alam", "rubber", "perkebunan", "40", "kontainer", "ekspor", "ton"),
    ("kopi", "Kopi", "coffee", "perkebunan", "09", "kontainer", "ekspor", "ton"),
    ("kakao", "Kakao", "cocoa|cokelat", "perkebunan", "18", "kontainer", "ekspor", "ton"),
    ("tembaga", "Konsentrat tembaga", "copper", "mineral", "26", "curah kering", "ekspor", "ton"),
    ("baja", "Produk baja", "steel|besi", "industri", "72", "break bulk", "domestik", "ton"),
    ("kayu", "Kayu olahan dan pulp", "timber|plywood|kayu lapis", "kehutanan", "44", "break bulk", "ekspor", "ton"),
    ("ikan", "Ikan dan udang beku", "tuna|udang|seafood|hasil laut", "perikanan", "03", "kontainer", "ekspor", "ton"),
    ("garmen", "Garmen dan tekstil", "pakaian|tekstil|textile", "manufaktur", "61", "kontainer", "ekspor", "ton"),
    ("elektronik", "Elektronik dan komponen", "electronics|komponen", "manufaktur", "85", "kontainer", "ekspor", "ton"),
    ("kendaraan", "Kendaraan bermotor", "mobil|otomotif|car", "manufaktur", "87", "ro-ro", "ekspor", "unit"),
]

# komoditas -> provinsi penghasil utama (ringkasan dari statistik produksi BPS / kementerian; urutan = bobot)
KOMODITAS_PROVINSI = {
    "batu_bara": ["ID-KI", "ID-KS", "ID-SS", "ID-JA"],
    "cpo": ["ID-RI", "ID-SU", "ID-KB", "ID-KT", "ID-JA", "ID-SS", "ID-KI"],
    "nikel": ["ID-ST", "ID-SG", "ID-MU"],
    "lng": ["ID-KI", "ID-PB"],
    "minyak_mentah": ["ID-RI", "ID-KI", "ID-JA", "ID-SS"],
    "bbm": ["ID-KI", "ID-JT", "ID-RI", "ID-JB"],
    "pupuk": ["ID-JI", "ID-KI", "ID-SS", "ID-AC"],
    "semen": ["ID-JB", "ID-SN", "ID-JI", "ID-SB", "ID-JT"],
    "beras": ["ID-JI", "ID-JB", "ID-JT", "ID-SN"],
    "gula": ["ID-JI", "ID-LA"],
    "bauksit": ["ID-KB", "ID-KR"],
    "karet": ["ID-SS", "ID-SU", "ID-JA", "ID-KB"],
    "kopi": ["ID-LA", "ID-SS", "ID-SU", "ID-AC"],
    "kakao": ["ID-SN", "ID-ST", "ID-SR"],
    "tembaga": ["ID-PT", "ID-NB"],
    "baja": ["ID-BT", "ID-JI"],
    "kayu": ["ID-KI", "ID-KB", "ID-RI"],
    "ikan": ["ID-MA", "ID-SA", "ID-PA", "ID-SN"],
    "garmen": ["ID-JB", "ID-JT"],
    "elektronik": ["ID-KR", "ID-JB"],
    "kendaraan": ["ID-JB", "ID-JK"],
}

# pelabuhan luar negeri yang lazim menjadi tujuan ekspor / asal impor tiap komoditas
PASAR_LUAR = {
    "batu_bara": ["CNTAO", "INMUN", "JPTYO", "KRPUS", "PHMNL", "VNSGN"],
    "cpo": ["INMUN", "CNSHA", "NLRTM", "MYPKG"],
    "nikel": ["CNSHA", "CNTAO", "JPTYO"],
    "lng": ["JPTYO", "KRPUS", "CNSHA", "TWKHH"],
    "minyak_mentah": ["SGSIN", "JPTYO", "THLCH"],
    "bbm": ["SGSIN", "MYPKG"],
    "beras": ["THLCH", "VNSGN"],
    "gula": ["THLCH", "INMUN"],
    "karet": ["CNSHA", "JPTYO", "KRPUS"],
    "kopi": ["JPTYO", "NLRTM", "SGSIN"],
    "kakao": ["MYPKG", "SGSIN", "NLRTM"],
    "tembaga": ["JPTYO", "KRPUS", "CNSHA"],
    "kayu": ["CNSHA", "JPTYO", "KRPUS"],
    "ikan": ["JPTYO", "CNSHA", "SGSIN"],
    "garmen": ["SGSIN", "NLRTM", "JPTYO"],
    "elektronik": ["SGSIN", "CNSHA", "KRPUS"],
    "kendaraan": ["PHMNL", "VNSGN", "JPTYO", "THLCH"],
}

# pelabuhan Indonesia yang menjadi tujuan utama kargo domestik / impor (hub konsumsi)
HUB_DOMESTIK = ["IDJKT", "IDSUB", "IDSRG", "IDBLW", "IDMAK", "IDBDJ", "IDBPN", "IDBIT", "IDAMQ", "IDSOQ", "IDKUP", "IDPTB", "IDCIG"]

JENIS_KAPAL = {"curah kering": "bulk carrier", "curah cair": "tanker", "gas": "LNG carrier",
               "kontainer": "kapal kontainer", "break bulk": "general cargo", "ro-ro": "ro-ro"}
DWT_RENTANG = {"bulk carrier": (28_000, 95_000), "tanker": (12_000, 110_000), "LNG carrier": (60_000, 85_000),
               "kapal kontainer": (9_000, 45_000), "general cargo": (5_000, 18_000), "ro-ro": (8_000, 20_000)}
KECEPATAN_KNOT = {"bulk carrier": 12.5, "tanker": 12.5, "LNG carrier": 17, "kapal kontainer": 16, "general cargo": 12, "ro-ro": 15}

NAMA_DEPAN = ["Bahari", "Nusantara", "Khatulistiwa", "Celebes", "Mahakam", "Kapuas", "Musi", "Barito", "Rinjani", "Semeru",
              "Krakatau", "Sinabung", "Bromo", "Merapi", "Tambora", "Halmahera", "Seram", "Sumba", "Flores", "Natuna",
              "Anambas", "Biak", "Arafura", "Banda", "Sawu", "Karimata", "Lombok", "Sunda", "Wakatobi", "Raja Ampat"]
NAMA_BELAKANG = ["Jaya", "Pioneer", "Express", "Spirit", "Glory", "Mandiri", "Perkasa", "Samudra", "Sentosa", "Abadi"]
NAMA_ASING = (["Meridian", "Pacific", "Oriental", "Eastern", "Golden", "Silver"],
              ["Dawn", "Star", "Horizon", "Crest", "Harmony", "Voyager", "Fortune", "Pearl", "Trader", "Venture"])
BENDERA_ASING = ["Singapura", "Panama", "Liberia", "Kepulauan Marshall", "Hong Kong", "Jepang"]

JENIS_INSIDEN = [("inspeksi PSC dengan temuan", 0.35), ("keterlambatan bongkar muat > 48 jam", 0.30),
                 ("dokumen muatan tidak lengkap", 0.15), ("kebocoran minor di dermaga", 0.08),
                 ("kandas di alur pelayaran", 0.07), ("penahanan sementara", 0.05)]
TINGKAT_INSIDEN = {"inspeksi PSC dengan temuan": "sedang", "keterlambatan bongkar muat > 48 jam": "rendah",
                   "dokumen muatan tidak lengkap": "sedang", "kebocoran minor di dermaga": "tinggi",
                   "kandas di alur pelayaran": "tinggi", "penahanan sementara": "tinggi"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tulis_csv(nama: str, kolom: list[str], baris: list) -> None:
    DIR_DATA.mkdir(parents=True, exist_ok=True)
    with open(DIR_DATA / nama, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(kolom)
        w.writerows(baris)
    print(f"  {nama:28s} {len(baris):5d} baris")


def bangun_kapal(rng: random.Random) -> list[list]:
    """Armada per perusahaan pelayaran/tambang/energi. Jenis kapal mengikuti moda komoditas yang ditangani."""
    moda = {k[0]: k[5] for k in KOMODITAS}
    kapal: list[list] = []
    nomor = 1
    jumlah_armada = {"pt_skl": 6, "pt_nbc": 7, "pt_kei": 6, "pt_mahakam_log": 4, "pt_andalas_tankers": 4, "pt_gas": 3,
                     "pt_tanker_bumi": 5, "pt_logistik_kep": 4, "pt_borneo": 2, "pt_nikel": 2, "pt_semen_jawa": 2,
                     "pt_pupuk_nusa": 2, "pt_kayu": 1, "pt_perikanan": 2, "meridian": 6, "pacific_ore": 4, "oriental_gas": 3}
    perusahaan = {p[0]: p for p in PERUSAHAAN}
    dipakai: set[str] = set()
    for pid, n in jumlah_armada.items():
        asing = perusahaan[pid][3] == "asing"
        jenis_pilihan = sorted({JENIS_KAPAL[moda[k]] for k in PERUSAHAAN_KOMODITAS[pid]})
        # kapal pertama tiap jenis dijamin ada supaya setiap komoditas perusahaan punya kapal yang cocok
        urutan_jenis = jenis_pilihan + [rng.choice(jenis_pilihan) for _ in range(max(0, n - len(jenis_pilihan)))]
        for jenis in urutan_jenis[:max(n, len(jenis_pilihan))]:
            dwt_min, dwt_max = DWT_RENTANG[jenis]
            dwt = int(round(rng.uniform(dwt_min, dwt_max), -2))
            while True:
                if asing:
                    nama = f"{rng.choice(NAMA_ASING[0])} {rng.choice(NAMA_ASING[1])}"
                else:
                    nama = f"{rng.choice(NAMA_DEPAN)} {rng.choice(NAMA_BELAKANG)}"
                if rng.random() < 0.35:
                    nama += f" {rng.randint(2, 9)}"
                if nama not in dipakai:
                    dipakai.add(nama)
                    break
            awalan = {"tanker": "MT", "LNG carrier": "LNG/C"}.get(jenis, "MV")
            bendera = rng.choice(BENDERA_ASING) if asing else ("Indonesia" if rng.random() < 0.92 else "Singapura")
            tahun = rng.randint(1998, 2024)
            panjang = int(round(40 + 0.0019 * dwt + rng.uniform(-8, 8)))
            kapal.append([f"KPL-{nomor:03d}", f"{awalan} {nama}", jenis, bendera, dwt, min(panjang, 300), tahun, pid])
            nomor += 1
    return kapal


def bangun_pelayaran(rng: random.Random, kapal: list[list], n: int) -> list[list]:
    """Rute mengikuti komoditas: asal dari provinsi penghasil, tujuan pasar luar negeri atau hub domestik."""
    pel = {p[0]: p for p in PELABUHAN}
    kom = {k[0]: k for k in KOMODITAS}
    kapal_per_jenis: dict[str, list[list]] = {}
    for k in kapal:
        kapal_per_jenis.setdefault(k[2], []).append(k)
    pelabuhan_di_prov: dict[str, list[str]] = {}
    for p in PELABUHAN:
        if p[5]:
            pelabuhan_di_prov.setdefault(p[5], []).append(p[0])
    # pengirim = perusahaan non-pelayaran yang menangani komoditas itu (jika ada), kalau tidak ada perusahaan apa pun
    jenis_perusahaan = {p[0]: p[2] for p in PERUSAHAAN}
    pengirim_per_kom: dict[str, list[str]] = {}
    for pid, daftar in PERUSAHAAN_KOMODITAS.items():
        for kid in daftar:
            pengirim_per_kom.setdefault(kid, []).append(pid)

    # bobot komoditas: energi dan sawit paling sering muncul, mirip komposisi ekspor Indonesia
    bobot = {"batu_bara": 14, "cpo": 10, "nikel": 8, "lng": 4, "minyak_mentah": 4, "bbm": 6, "pupuk": 5, "semen": 6,
             "beras": 3, "gula": 2, "bauksit": 3, "karet": 3, "kopi": 2, "kakao": 2, "tembaga": 3, "baja": 3,
             "kayu": 3, "ikan": 4, "garmen": 4, "elektronik": 4, "kendaraan": 4}
    ids = list(bobot)
    mulai, akhir = date(2024, 1, 1), date(2026, 12, 15)
    rentang = (akhir - mulai).days
    pelayaran: list[list] = []
    for i in range(1, n + 1):
        kid = rng.choices(ids, weights=[bobot[k] for k in ids])[0]
        k = kom[kid]
        jenis_kapal = JENIS_KAPAL[k[5]]
        arah = k[6]
        internasional = (arah == "ekspor" and rng.random() < 0.65) or (arah == "impor" and rng.random() < 0.8) \
            or (arah == "campuran" and rng.random() < 0.5)
        prov_asal = rng.choice(KOMODITAS_PROVINSI[kid])
        kandidat_asal = pelabuhan_di_prov.get(prov_asal) or HUB_DOMESTIK
        if internasional and arah == "impor":
            asal = rng.choice(PASAR_LUAR[kid])
            tujuan = rng.choice(HUB_DOMESTIK[:7])
        elif internasional:
            asal = rng.choice(kandidat_asal)
            tujuan = rng.choice(PASAR_LUAR[kid])
        else:
            asal = rng.choice(kandidat_asal)
            tujuan = rng.choice([h for h in HUB_DOMESTIK if h != asal])
        # cabotage: rute domestik hanya kapal berbendera Indonesia
        armada = [kp for kp in kapal_per_jenis[jenis_kapal] if internasional or kp[3] == "Indonesia"]
        kp = rng.choice(armada or kapal_per_jenis[jenis_kapal])
        a, t = pel[asal], pel[tujuan]
        jarak = haversine_km(a[8], a[9], t[8], t[9]) * 1.25   # faktor rute laut tidak lurus
        jam = jarak / (KECEPATAN_KNOT[jenis_kapal] * 1.852)
        durasi = max(1, int(round(jam / 24 + rng.uniform(1.0, 3.0))))  # + hari tunggu/bongkar muat
        berangkat = mulai + timedelta(days=rng.randint(0, rentang))
        tiba = berangkat + timedelta(days=durasi)
        if tiba <= HARI_INI:
            status = "selesai"
        elif berangkat <= HARI_INI:
            status = "berlayar"
        else:
            status = "dijadwalkan"
        muatan = int(round(kp[4] * rng.uniform(0.55, 0.95), -2))
        if k[7] == "unit":
            muatan = int(round(kp[4] / 12 * rng.uniform(0.6, 0.95), -1))
        kandidat_pengirim = [p for p in pengirim_per_kom.get(kid, []) if jenis_perusahaan[p] != "pelayaran"] \
            or pengirim_per_kom.get(kid, [kp[7]])
        pengirim = rng.choice(kandidat_pengirim)
        pelayaran.append([f"VOY-{i:04d}", kp[0], asal, tujuan, kid, pengirim, berangkat.isoformat(), tiba.isoformat(),
                          muatan, int(round(jarak)), status])
    return pelayaran


def bangun_insiden(rng: random.Random, kapal: list[list], pelayaran: list[list], n: int) -> list[list]:
    """Kapal tua dan berbendera asing lebih sering kena insiden; lokasi dan tanggal diambil dari pelayarannya."""
    pelayaran_kapal: dict[str, list[list]] = {}
    for v in pelayaran:
        if v[10] != "dijadwalkan":
            pelayaran_kapal.setdefault(v[1], []).append(v)
    kandidat = [k for k in kapal if k[0] in pelayaran_kapal]
    bobot = [(2026 - k[6]) * (1.6 if k[3] != "Indonesia" else 1.0) + 2 for k in kandidat]
    jenis = [j for j, _ in JENIS_INSIDEN]
    bobot_jenis = [b for _, b in JENIS_INSIDEN]
    insiden: list[list] = []
    for i in range(1, n + 1):
        k = rng.choices(kandidat, weights=bobot)[0]
        v = rng.choice(pelayaran_kapal[k[0]])
        di_tujuan = rng.random() < 0.6
        pelabuhan = v[3] if di_tujuan else v[2]
        tanggal = date.fromisoformat(v[7]) if di_tujuan else date.fromisoformat(v[6])
        if tanggal > HARI_INI:
            tanggal = date.fromisoformat(v[6])
        j = rng.choices(jenis, weights=bobot_jenis)[0]
        hari_tertahan = {"rendah": rng.randint(1, 3), "sedang": rng.randint(1, 6), "tinggi": rng.randint(3, 21)}[TINGKAT_INSIDEN[j]]
        insiden.append([f"INS-{i:03d}", k[0], pelabuhan, v[0], tanggal.isoformat(), j, TINGKAT_INSIDEN[j], hari_tertahan])
    insiden.sort(key=lambda r: r[4])
    return [[f"INS-{i:03d}", *r[1:]] for i, r in enumerate(insiden, 1)]


KOLOM_LENGKAP = ["id", "berangkat", "tiba", "status", "kapal", "jenis_kapal", "bendera", "dwt", "pemilik", "asal", "negara_asal",
                 "tujuan", "negara_tujuan", "komoditas", "kategori_komoditas", "pengirim", "muatan", "jarak_km"]


def pelayaran_lengkap(kapal: list[list], pelayaran: list[list]) -> list[list]:
    """Tampilan datar (denormalisasi) pelayaran dengan nama, bukan id: untuk analisis di luar aplikasi, misalnya pandas atau chatbot."""
    kp = {k[0]: k for k in kapal}
    pel = {p[0]: p for p in PELABUHAN}
    kom = {k[0]: k for k in KOMODITAS}
    per = {p[0]: p for p in PERUSAHAAN}
    hasil = []
    for v in pelayaran:
        k, a, t, c = kp[v[1]], pel[v[2]], pel[v[3]], kom[v[4]]
        hasil.append([v[0], v[6], v[7], v[10], k[1], k[2], k[3], k[4], per[k[7]][1], a[1], a[4], t[1], t[4], c[1], c[3],
                      per[v[5]][1], v[8], v[9]])
    return hasil


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pelayaran", type=int, default=520)
    ap.add_argument("--insiden", type=int, default=90)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    print(f"Menulis data ke {DIR_DATA} (seed {args.seed})")
    tulis_csv("provinsi.csv", ["id", "nama", "alias", "pulau", "ibu_kota", "lat", "lon", "penduduk_juta"], PROVINSI)
    tulis_csv("perusahaan.csv", ["id", "nama", "alias", "jenis", "kepemilikan", "negara", "provinsi_id", "induk_id",
                                 "tahun_berdiri", "deskripsi"],
              [[p[0], p[1], ALIAS_PERUSAHAAN.get(p[0], ""), *p[2:]] for p in PERUSAHAAN])
    tulis_csv("perusahaan_komoditas.csv", ["perusahaan_id", "komoditas_id"],
              [[p, k] for p, daftar in PERUSAHAAN_KOMODITAS.items() for k in daftar])
    tulis_csv("pelabuhan.csv", ["id", "nama", "alias", "kota", "negara", "provinsi_id", "operator_id", "kelas", "lat", "lon"],
              PELABUHAN)
    tulis_csv("komoditas.csv", ["id", "nama", "alias", "kategori", "hs_bab", "moda", "arah", "satuan"], KOMODITAS)
    tulis_csv("komoditas_provinsi.csv", ["komoditas_id", "provinsi_id", "peringkat"],
              [[k, p, i + 1] for k, daftar in KOMODITAS_PROVINSI.items() for i, p in enumerate(daftar)])
    kapal = bangun_kapal(rng)
    tulis_csv("kapal.csv", ["id", "nama", "alias", "jenis", "bendera", "dwt", "panjang_m", "tahun_dibangun", "pemilik_id"],
              [[k[0], k[1], k[1].split(" ", 1)[1], *k[2:]] for k in kapal])
    pelayaran = bangun_pelayaran(rng, kapal, args.pelayaran)
    tulis_csv("pelayaran.csv", ["id", "kapal_id", "asal_id", "tujuan_id", "komoditas_id", "pengirim_id", "berangkat", "tiba",
                                "muatan", "jarak_km", "status"], pelayaran)
    insiden = bangun_insiden(rng, kapal, pelayaran, args.insiden)
    tulis_csv("insiden.csv", ["id", "kapal_id", "pelabuhan_id", "pelayaran_id", "tanggal", "jenis", "tingkat", "hari_tertahan"],
              insiden)
    tulis_csv("pelayaran_lengkap.csv", KOLOM_LENGKAP, pelayaran_lengkap(kapal, pelayaran))
    print("Selesai.")


if __name__ == "__main__":
    main()
