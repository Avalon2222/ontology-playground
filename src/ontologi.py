"""
ontologi.py - Definisi ontologi: tipe objek, properti, dan tipe tautan (link).

Ini lapisan "makna" di atas tabel SQLite. Setiap TipeObjek menunjuk ke satu tabel dan menjelaskan
propertinya; setiap TipeTautan menjelaskan relasi antar dua tipe objek dan tabel/kolom mana yang
menyimpannya. Modul lain (basis_data, kueri, graf, app) tidak pernah menulis nama tabel sendiri;
semuanya bertanya ke sini. Karena itu menambah tipe objek atau tautan baru hanya perlu menyentuh
file ini (plus CSV-nya).

Konsepnya meniru ontologi ala Palantir Foundry: object type, property, link type, dan object set.
Istilah Indonesia yang dipakai di sini: tipe objek, properti, tipe tautan, dan himpunan objek.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Properti:
    nama: str                 # nama kolom di tabel
    label: str                # label yang ditampilkan
    tipe: str                 # teks | angka | tanggal | kategori | koordinat | id
    deskripsi: str = ""
    satuan: str = ""


@dataclass(frozen=True)
class TipeObjek:
    id: str                   # nama tabel sekaligus id tipe
    label: str
    label_jamak: str
    ikon: str
    warna: str
    deskripsi: str
    properti: tuple[Properti, ...]
    sinonim: tuple[str, ...] = ()     # kata dalam pertanyaan yang menunjuk tipe ini
    kolom_judul: str = "nama"         # kolom yang dipakai sebagai judul objek
    kolom_alias: str = ""             # kolom alias (dipisah '|') untuk pencarian nama
    asal: str = "nyata"               # nyata | sintetis (keterangan sumber data)

    @property
    def tabel(self) -> str:
        return self.id

    def properti_dict(self) -> dict[str, Properti]:
        return {p.nama: p for p in self.properti}

    def kategori(self) -> list[Properti]:
        return [p for p in self.properti if p.tipe == "kategori"]

    def angka(self) -> list[Properti]:
        return [p for p in self.properti if p.tipe == "angka"]


@dataclass(frozen=True)
class TipeTautan:
    id: str
    label: str                # dibaca dari sumber ke tujuan: Kapal "dimiliki oleh" Perusahaan
    label_balik: str          # dibaca dari tujuan ke sumber: Perusahaan "memiliki" Kapal
    sumber: str               # id tipe objek
    tujuan: str               # id tipe objek
    tabel: str                # tabel yang menyimpan pasangan (tabel sumber sendiri atau tabel penghubung)
    kolom_sumber: str         # kolom di `tabel` yang berisi id objek sumber
    kolom_tujuan: str         # kolom di `tabel` yang berisi id objek tujuan
    kardinalitas: str = "N:1"
    deskripsi: str = ""
    kata_kunci: tuple[str, ...] = field(default_factory=tuple)   # petunjuk dalam pertanyaan untuk memilih tautan ini

    def ujung_lain(self, tipe: str) -> str:
        return self.tujuan if tipe == self.sumber else self.sumber

    def label_dari(self, tipe: str) -> str:
        """Label yang tepat kalau tautan dibaca mulai dari `tipe`."""
        return self.label if tipe == self.sumber else self.label_balik


# ---------------------------------------------------------------------------
# TIPE OBJEK
# ---------------------------------------------------------------------------
TIPE_OBJEK: dict[str, TipeObjek] = {}
TIPE_TAUTAN: dict[str, TipeTautan] = {}


def _objek(t: TipeObjek) -> None:
    TIPE_OBJEK[t.id] = t


def _tautan(t: TipeTautan) -> None:
    assert t.sumber in TIPE_OBJEK and t.tujuan in TIPE_OBJEK, t.id
    TIPE_TAUTAN[t.id] = t


_objek(TipeObjek(
    "provinsi", "Provinsi", "Provinsi", "🗺️", "#34d399",
    "38 provinsi Indonesia dengan ibu kota, pulau, dan jumlah penduduk (BPS).",
    (Properti("id", "Kode", "id", "kode ISO 3166-2"),
     Properti("nama", "Nama", "teks"),
     Properti("alias", "Alias", "teks", "singkatan umum, dipisah |"),
     Properti("pulau", "Pulau / kawasan", "kategori"),
     Properti("ibu_kota", "Ibu kota", "teks"),
     Properti("lat", "Lintang", "koordinat"), Properti("lon", "Bujur", "koordinat"),
     Properti("penduduk_juta", "Penduduk", "angka", "pertengahan 2023", "juta jiwa")),
    sinonim=("provinsi", "daerah", "wilayah", "province"), kolom_alias="alias",
))

_objek(TipeObjek(
    "perusahaan", "Perusahaan", "Perusahaan", "🏢", "#f472b6",
    "Operator pelabuhan (nyata) dan perusahaan pelayaran, tambang, perkebunan, industri (fiktif).",
    (Properti("id", "ID", "id"),
     Properti("nama", "Nama", "teks"),
     Properti("alias", "Alias", "teks", "nama pendek, dipisah |"),
     Properti("jenis", "Jenis usaha", "kategori"),
     Properti("kepemilikan", "Kepemilikan", "kategori", "BUMN, swasta, asing, patungan, pemerintah"),
     Properti("negara", "Negara kantor pusat", "kategori"),
     Properti("tahun_berdiri", "Tahun berdiri", "angka"),
     Properti("deskripsi", "Deskripsi", "teks")),
    sinonim=("perusahaan", "pemilik", "operator", "company", "pt", "holding", "grup", "group", "pengirim", "shipper",
             "anak usaha", "anak perusahaan", "induk", "induk usaha"),
    kolom_alias="alias", asal="campuran",
))

_objek(TipeObjek(
    "komoditas", "Komoditas", "Komoditas", "📦", "#fbbf24",
    "21 komoditas utama perdagangan laut Indonesia dengan bab HS, moda angkut, dan arah perdagangan.",
    (Properti("id", "ID", "id"),
     Properti("nama", "Nama", "teks"),
     Properti("alias", "Alias", "teks"),
     Properti("kategori", "Kategori", "kategori", "energi, mineral, perkebunan, pangan, industri, manufaktur, perikanan, kehutanan"),
     Properti("hs_bab", "Bab HS", "teks", "dua digit pertama kode Harmonized System"),
     Properti("moda", "Moda angkut", "kategori", "menentukan jenis kapal: curah kering, curah cair, gas, kontainer, break bulk, ro-ro"),
     Properti("arah", "Arah perdagangan", "kategori", "ekspor, impor, domestik, campuran"),
     Properti("satuan", "Satuan", "teks")),
    sinonim=("komoditas", "barang", "muatan", "kargo", "cargo", "commodity", "produk"), kolom_alias="alias",
))

_objek(TipeObjek(
    "pelabuhan", "Pelabuhan", "Pelabuhan", "⚓", "#22d3ee",
    "30 pelabuhan Indonesia dan 12 hub luar negeri, kode UN/LOCODE, operator, kelas, koordinat.",
    (Properti("id", "LOCODE", "id", "kode UN/LOCODE"),
     Properti("nama", "Nama", "teks"),
     Properti("alias", "Alias", "teks"),
     Properti("kota", "Kota", "teks"),
     Properti("negara", "Negara", "kategori"),
     Properti("kelas", "Kelas", "kategori", "utama internasional, utama, pengumpul, hub internasional"),
     Properti("lat", "Lintang", "koordinat"), Properti("lon", "Bujur", "koordinat")),
    sinonim=("pelabuhan", "port", "dermaga", "terminal", "hub"), kolom_alias="alias",
))

_objek(TipeObjek(
    "kapal", "Kapal", "Kapal", "🚢", "#60a5fa",
    "Armada 63 kapal (sintetis): jenis, bendera, bobot mati, tahun dibangun, pemilik.",
    (Properti("id", "ID", "id"),
     Properti("nama", "Nama", "teks"),
     Properti("alias", "Nama tanpa awalan", "teks"),
     Properti("jenis", "Jenis kapal", "kategori", "bulk carrier, tanker, LNG carrier, kapal kontainer, general cargo, ro-ro"),
     Properti("bendera", "Bendera", "kategori"),
     Properti("dwt", "Bobot mati (DWT)", "angka", "deadweight tonnage", "ton"),
     Properti("panjang_m", "Panjang", "angka", "", "m"),
     Properti("tahun_dibangun", "Tahun dibangun", "angka")),
    sinonim=("kapal", "vessel", "ship", "tanker", "armada", "fleet", "tongkang"), kolom_alias="alias", asal="sintetis",
))

_objek(TipeObjek(
    "pelayaran", "Pelayaran", "Pelayaran", "🧭", "#a78bfa",
    "520 pelayaran (sintetis) 2024-2026: kapal, asal, tujuan, komoditas, pengirim, tanggal, muatan.",
    (Properti("id", "ID", "id"),
     Properti("berangkat", "Berangkat", "tanggal"),
     Properti("tiba", "Tiba", "tanggal"),
     Properti("muatan", "Muatan", "angka", "ton, atau unit untuk kendaraan", "ton"),
     Properti("jarak_km", "Jarak", "angka", "perkiraan jarak laut", "km"),
     Properti("status", "Status", "kategori", "selesai, berlayar, dijadwalkan")),
    sinonim=("pelayaran", "perjalanan", "voyage", "rute", "pengiriman", "pengapalan", "trip", "shipment", "pengangkutan"),
    kolom_judul="id", asal="sintetis",
))

_objek(TipeObjek(
    "insiden", "Insiden", "Insiden", "⚠️", "#f87171",
    "90 insiden (sintetis) di pelabuhan: temuan inspeksi, keterlambatan, kandas, penahanan.",
    (Properti("id", "ID", "id"),
     Properti("tanggal", "Tanggal", "tanggal"),
     Properti("jenis", "Jenis", "kategori"),
     Properti("tingkat", "Tingkat", "kategori", "rendah, sedang, tinggi"),
     Properti("hari_tertahan", "Hari tertahan", "angka", "", "hari")),
    sinonim=("insiden", "kejadian", "inspeksi", "masalah", "incident", "pelanggaran", "kecelakaan", "temuan"),
    kolom_judul="id", asal="sintetis",
))

# ---------------------------------------------------------------------------
# TIPE TAUTAN
# ---------------------------------------------------------------------------
_tautan(TipeTautan("pelabuhan_terletak_di", "terletak di", "memiliki pelabuhan", "pelabuhan", "provinsi",
                   "pelabuhan", "id", "provinsi_id", "N:1", "Pelabuhan Indonesia dan provinsinya.",
                   ("terletak", "berada", "di provinsi")))
_tautan(TipeTautan("pelabuhan_dioperasikan_oleh", "dioperasikan oleh", "mengoperasikan", "pelabuhan", "perusahaan",
                   "pelabuhan", "id", "operator_id", "N:1", "Operator terminal (Pelindo regional, BP Batam, dan lainnya).",
                   ("dioperasikan", "operator", "mengoperasikan", "dikelola", "pengelola")))
_tautan(TipeTautan("perusahaan_berkantor_di", "berkantor di", "menjadi kantor pusat", "perusahaan", "provinsi",
                   "perusahaan", "id", "provinsi_id", "N:1", "Provinsi kantor pusat perusahaan Indonesia.",
                   ("berkantor", "kantor pusat", "berbasis", "bermarkas")))
_tautan(TipeTautan("perusahaan_anak_dari", "anak usaha dari", "induk dari", "perusahaan", "perusahaan",
                   "perusahaan", "id", "induk_id", "N:1", "Struktur grup: anak usaha dan induknya.",
                   ("anak usaha", "induk", "grup", "holding", "subsidiary", "parent")))
_tautan(TipeTautan("perusahaan_bergerak_di", "bergerak di komoditas", "ditangani oleh", "perusahaan", "komoditas",
                   "perusahaan_komoditas", "perusahaan_id", "komoditas_id", "N:N",
                   "Komoditas yang diproduksi, diperdagangkan, atau diangkut perusahaan.",
                   ("bergerak", "menangani", "memproduksi", "memperdagangkan", "bisnis")))
_tautan(TipeTautan("kapal_dimiliki_oleh", "dimiliki oleh", "memiliki kapal", "kapal", "perusahaan",
                   "kapal", "id", "pemilik_id", "N:1", "Pemilik atau operator kapal.",
                   ("dimiliki", "pemilik", "milik", "punya", "memiliki", "owner")))
_tautan(TipeTautan("pelayaran_memakai", "memakai kapal", "melakukan pelayaran", "pelayaran", "kapal",
                   "pelayaran", "id", "kapal_id", "N:1", "Kapal yang menjalani pelayaran.",
                   ("memakai", "menggunakan", "dengan kapal", "dilayani")))
_tautan(TipeTautan("pelayaran_berangkat_dari", "berangkat dari", "menjadi asal pelayaran", "pelayaran", "pelabuhan",
                   "pelayaran", "id", "asal_id", "N:1", "Pelabuhan asal.",
                   ("berangkat", "dari", "asal", "keluar", "ekspor dari", "berasal", "departs")))
_tautan(TipeTautan("pelayaran_tiba_di", "tiba di", "menjadi tujuan pelayaran", "pelayaran", "pelabuhan",
                   "pelayaran", "id", "tujuan_id", "N:1", "Pelabuhan tujuan.",
                   ("tiba", "ke", "tujuan", "menuju", "masuk", "sampai", "arrives", "datang", "mendarat")))
_tautan(TipeTautan("pelayaran_mengangkut", "mengangkut", "diangkut dalam pelayaran", "pelayaran", "komoditas",
                   "pelayaran", "id", "komoditas_id", "N:1", "Komoditas yang dimuat.",
                   ("mengangkut", "membawa", "memuat", "bermuatan", "diangkut", "dibawa", "dikirim")))
_tautan(TipeTautan("pelayaran_dikirim_oleh", "dikirim oleh", "mengirim lewat pelayaran", "pelayaran", "perusahaan",
                   "pelayaran", "id", "pengirim_id", "N:1", "Perusahaan pengirim (shipper) muatan.",
                   ("dikirim", "pengirim", "mengirim", "shipper", "mengekspor", "mengimpor")))
_tautan(TipeTautan("komoditas_diproduksi_di", "diproduksi di", "menghasilkan komoditas", "komoditas", "provinsi",
                   "komoditas_provinsi", "komoditas_id", "provinsi_id", "N:N", "Provinsi penghasil utama (peringkat 1 = terbesar).",
                   ("diproduksi", "dihasilkan", "penghasil", "produksi", "menghasilkan", "ditambang", "ditanam")))
_tautan(TipeTautan("insiden_melibatkan", "melibatkan kapal", "mengalami insiden", "insiden", "kapal",
                   "insiden", "id", "kapal_id", "N:1", "Kapal yang terlibat insiden.",
                   ("melibatkan", "mengalami", "terlibat", "kena")))
_tautan(TipeTautan("insiden_terjadi_di", "terjadi di", "menjadi lokasi insiden", "insiden", "pelabuhan",
                   "insiden", "id", "pelabuhan_id", "N:1", "Pelabuhan lokasi insiden.",
                   ("terjadi", "lokasi", "tempat")))
_tautan(TipeTautan("insiden_saat_pelayaran", "saat pelayaran", "mencatat insiden", "insiden", "pelayaran",
                   "insiden", "id", "pelayaran_id", "N:1", "Pelayaran ketika insiden terjadi.",
                   ("saat", "ketika", "selama")))


# ---------------------------------------------------------------------------
# NAVIGASI SKEMA
# ---------------------------------------------------------------------------
def tautan_tipe(tipe: str) -> list[TipeTautan]:
    """Semua tautan yang menyentuh tipe objek ini, dalam arah mana pun."""
    return [t for t in TIPE_TAUTAN.values() if tipe in (t.sumber, t.tujuan)]


def tautan_antara(a: str, b: str) -> list[TipeTautan]:
    """Tautan langsung antara dua tipe (bisa lebih dari satu, misalnya pelayaran-pelabuhan: asal dan tujuan)."""
    return [t for t in TIPE_TAUTAN.values() if {t.sumber, t.tujuan} == {a, b} or (a == b and t.sumber == t.tujuan == a)]


def tetangga_tipe(tipe: str) -> dict[str, list[TipeTautan]]:
    """Tipe objek lain yang terhubung langsung, dikelompokkan per tipe."""
    hasil: dict[str, list[TipeTautan]] = {}
    for t in tautan_tipe(tipe):
        hasil.setdefault(t.ujung_lain(tipe), []).append(t)
    return hasil


def jalur_terpendek(dari: str, ke: str) -> list[str] | None:
    """BFS pada graf skema: urutan tipe objek dari `dari` ke `ke`. [dari] kalau sama, None kalau tak terhubung."""
    if dari == ke:
        return [dari]
    antrean = deque([[dari]])
    dikunjungi = {dari}
    while antrean:
        jalur = antrean.popleft()
        for lanjut in tetangga_tipe(jalur[-1]):
            if lanjut in dikunjungi:
                continue
            if lanjut == ke:
                return jalur + [lanjut]
            dikunjungi.add(lanjut)
            antrean.append(jalur + [lanjut])
    return None


def dot_skema(jumlah: dict[str, int] | None = None, sorot: str | None = None) -> str:
    """Diagram skema dalam bahasa DOT (Graphviz) untuk st.graphviz_chart: kotak = tipe objek, panah = tipe tautan."""
    jumlah = jumlah or {}
    baris = ["digraph ontologi {", '  rankdir=TB; bgcolor="transparent"; pad=0.3; nodesep=0.9; ranksep=0.7;',
             '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=12 color="#1f2a3c" fontcolor="#0b1020" penwidth=1.2];',
             '  edge [fontname="Helvetica" fontsize=9 color="#7d8aa0" fontcolor="#c3ccd9" arrowsize=0.7];']
    for t in TIPE_OBJEK.values():
        n = jumlah.get(t.id)
        label = f"{t.ikon} {t.label}" + (f"\\n{n:,} objek".replace(",", ".") if n is not None else "")
        pen = 3 if sorot == t.id else 1.2
        baris.append(f'  {t.id} [label="{label}" fillcolor="{t.warna}" penwidth={pen}];')
    for l in TIPE_TAUTAN.values():
        baris.append(f'  {l.sumber} -> {l.tujuan} [label="{l.label}"];')
    baris.append("}")
    return "\n".join(baris)


def ringkasan_skema() -> str:
    """Teks ringkas skema untuk ditampilkan atau dipakai sebagai konteks."""
    bagian = []
    for t in TIPE_OBJEK.values():
        props = ", ".join(f"{p.nama} ({p.tipe})" for p in t.properti)
        bagian.append(f"{t.ikon} {t.label}: {props}")
    bagian.append("")
    for l in TIPE_TAUTAN.values():
        bagian.append(f"{TIPE_OBJEK[l.sumber].label} --{l.label}--> {TIPE_OBJEK[l.tujuan].label} [{l.kardinalitas}]")
    return "\n".join(bagian)
