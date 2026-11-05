"""
kueri.py - Mengubah pertanyaan bahasa sehari-hari menjadi "himpunan objek" lalu SQL, dipandu ontologi.

Tidak ada model bahasa di sini. Mesinnya deterministik dan bisa dibaca:

1. Kenali ENTITAS: nama/alias objek yang disebut (Balikpapan, batu bara, Nusantara Bulk, Kaltim, KPL-057).
2. Kenali TIPE TARGET: tipe objek yang ditanyakan (kapal, pelabuhan, komoditas, ...), lewat sinonim.
3. Tentukan MAKSUD: daftar, hitung (berapa), peringkat (terbanyak), ekstrem (terbesar/tertua), detail.
4. Cari JALUR di graf skema ontologi dari tipe target ke tipe entitas (BFS), pilih tautan yang cocok dengan
   kata petunjuk di pertanyaan ("dari" -> berangkat dari, "ke" -> tiba di).
5. Susun SQL: SELECT DISTINCT objek target JOIN sepanjang jalur WHERE entitas = ... plus filter (tahun, kategori).

Hasilnya adalah `Rencana` yang berisi SQL, parameter, dan penjelasan langkah demi langkah. Konsep ini sama dengan
"search around" / "object set" di Palantir Foundry: setiap pertanyaan adalah himpunan objek yang didapat dengan
melompat lewat tautan dari objek yang disebut.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from itertools import product

import pandas as pd

from src import basis_data, ontologi
from src.ontologi import TIPE_OBJEK, TIPE_TAUTAN, TipeTautan

BATAS_DAFTAR = 50
BATAS_PERINGKAT = 10

KATA_HITUNG = ("berapa", "jumlah", "banyaknya", "how many", "count", "total")
KATA_PERINGKAT = ("terbanyak", "paling banyak", "tersibuk", "paling sibuk", "paling sering", "paling ramai", "teratas",
                  "top", "terpopuler", "paling aktif", "tertinggi jumlah", "paling banyak")
KATA_RUJUK = ("itu", "tersebut", "nya", "dia", "mereka", "tadi", "sama", "juga")
KATA_DETAIL = ("siapa", "di mana", "dimana", "info", "profil", "tentang", "apa itu", "detail", "jelaskan", "ceritakan")

# superlatif properti: (kata, tipe objek, kolom, arah)
SUPERLATIF_PROPERTI = [
    ("terbesar", "kapal", "dwt", "DESC"), ("paling besar", "kapal", "dwt", "DESC"), ("terkecil", "kapal", "dwt", "ASC"),
    ("tertua", "kapal", "tahun_dibangun", "ASC"), ("paling tua", "kapal", "tahun_dibangun", "ASC"),
    ("terbaru", "kapal", "tahun_dibangun", "DESC"), ("termuda", "kapal", "tahun_dibangun", "DESC"),
    ("terpanjang", "kapal", "panjang_m", "DESC"),
    ("terjauh", "pelayaran", "jarak_km", "DESC"), ("terdekat", "pelayaran", "jarak_km", "ASC"),
    ("terbesar", "pelayaran", "muatan", "DESC"), ("terberat", "pelayaran", "muatan", "DESC"),
    ("terpadat", "provinsi", "penduduk_juta", "DESC"), ("terbesar", "provinsi", "penduduk_juta", "DESC"),
    ("terkecil", "provinsi", "penduduk_juta", "ASC"),
    ("tertua", "perusahaan", "tahun_berdiri", "ASC"), ("terbaru", "perusahaan", "tahun_berdiri", "DESC"),
    ("terlama", "insiden", "hari_tertahan", "DESC"), ("terparah", "insiden", "hari_tertahan", "DESC"),
]
KOLOM_TAHUN = {"pelayaran": "berangkat", "insiden": "tanggal", "kapal": "tahun_dibangun", "perusahaan": "tahun_berdiri"}
# kata pembalik arah untuk tautan ke tipe sendiri (perusahaan -> perusahaan)
KATA_INDUK = ("induk", "holding", "pemilik", "parent", "membawahi", "menguasai")
KATA_ANAK = ("anak", "di bawah", "dimiliki", "subsidiary", "bagian dari")
STOP_ENTITAS = {"indonesia"}   # nama yang terlalu umum untuk dianggap entitas


@dataclass
class Entitas:
    tipe: str
    id: str
    nama: str
    teks: str                  # potongan teks yang cocok
    posisi: int                # indeks kata awal
    petunjuk: str = ""         # kata-kata di sekitar entitas (untuk memilih tautan)


@dataclass
class Filter:
    tipe: str
    kolom: str
    operator: str              # =, <>, >=, <=, tahun
    nilai: str
    label: str


@dataclass
class Rencana:
    pertanyaan: str
    maksud: str = "bantuan"                  # daftar | hitung | peringkat | ekstrem | detail | bantuan
    tipe_target: str | None = None
    jangkar: list[Entitas] = field(default_factory=list)
    jalur: list[list[str]] = field(default_factory=list)            # per jangkar: urutan tipe
    tautan_jalur: list[list[list[TipeTautan]]] = field(default_factory=list)   # per jangkar, per langkah
    filter: list[Filter] = field(default_factory=list)
    tipe_ukur: str | None = None             # untuk peringkat: tipe yang dihitung
    urut: tuple[str, str] | None = None      # untuk ekstrem: (kolom, arah)
    sql: str = ""
    params: list = field(default_factory=list)
    penjelasan: list[str] = field(default_factory=list)
    catatan: str = ""


# ---------------------------------------------------------------------------
# 1. INDEKS ENTITAS
# ---------------------------------------------------------------------------
_INDEKS: dict[int, list[tuple[str, str, str, str]]] = {}


def _normal(teks: str) -> str:
    teks = teks.lower().replace("?", " ").replace(",", " ").replace(".", " ").replace("!", " ")
    teks = re.sub(r"[\"'()]", " ", teks)
    return re.sub(r"\s+", " ", teks).strip()


def indeks_entitas(kon: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    """[(teks_cocok, tipe, id, nama)] diurutkan dari teks terpanjang supaya pencocokan 'rakus'."""
    if id(kon) in _INDEKS:
        return _INDEKS[id(kon)]
    daftar: list[tuple[str, str, str, str]] = []
    for t in TIPE_OBJEK.values():
        df = basis_data.semua_objek(kon, t.id)
        for _, r in df.iterrows():
            varian = {str(r["id"])}
            if t.kolom_judul != "id":
                nama = str(r[t.kolom_judul])
                varian.add(nama)
                for awalan in ("pt ", "mv ", "mt ", "lng/c "):
                    if nama.lower().startswith(awalan):
                        varian.add(nama[len(awalan):])
                varian.add(re.sub(r"\s*\(persero\)", "", nama, flags=re.I))
            if t.kolom_alias and str(r[t.kolom_alias]):
                varian.update(a for a in str(r[t.kolom_alias]).split("|") if a)
            for v in varian:
                v = _normal(v)
                if len(v) >= 3 and v not in STOP_ENTITAS:
                    daftar.append((v, t.id, str(r["id"]), str(r[t.kolom_judul])))
    daftar.sort(key=lambda x: -len(x[0]))
    _INDEKS[id(kon)] = daftar
    return daftar


def kenali_entitas(kon: sqlite3.Connection, teks: str) -> tuple[list[Entitas], str]:
    """Temukan entitas dalam teks; kembalikan daftar entitas dan teks sisa (entitas diganti spasi)."""
    sisa = f" {teks} "
    entitas: list[Entitas] = []
    for cocok, tipe, id_objek, nama in indeks_entitas(kon):
        pola = re.compile(r"(?<![\w-])" + re.escape(cocok) + r"(?![\w-])")
        m = pola.search(sisa)
        if not m:
            continue
        if any(e.id == id_objek and e.tipe == tipe for e in entitas):
            sisa = sisa[:m.start()] + " " * (m.end() - m.start()) + sisa[m.end():]
            continue
        posisi = len(sisa[:m.start()].split())
        sebelum = " ".join(sisa[:m.start()].split()[-3:])
        entitas.append(Entitas(tipe, id_objek, nama, cocok, posisi, sebelum))
        sisa = sisa[:m.start()] + " " * (m.end() - m.start()) + sisa[m.end():]
    entitas.sort(key=lambda e: e.posisi)
    return entitas, re.sub(r"\s+", " ", sisa).strip()


# ---------------------------------------------------------------------------
# 2. TIPE TARGET, MAKSUD, FILTER
# ---------------------------------------------------------------------------
def kenali_tipe(teks: str) -> list[tuple[int, str, str]]:
    """Semua sebutan tipe objek dalam teks: [(posisi, tipe, kata)] urut posisi."""
    hasil = []
    kata = teks.split()
    for t in TIPE_OBJEK.values():
        for s in t.sinonim + (t.label.lower(), t.label_jamak.lower()):
            for m in re.finditer(r"(?<!\w)" + re.escape(s) + r"(?!\w)", teks):
                hasil.append((len(teks[:m.start()].split()), t.id, s))
    hasil.sort()
    # buang duplikat posisi (sinonim yang saling mengandung)
    bersih, terpakai = [], set()
    for pos, tipe, s in hasil:
        if pos not in terpakai:
            bersih.append((pos, tipe, s))
            terpakai.add(pos)
    return bersih if kata else []


_NILAI_KATEGORI: dict[int, list[tuple[str, str, str]]] = {}


def nilai_kategori(kon: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """Semua nilai properti kategori di basis data: [(nilai_lower, tipe, kolom)], terpanjang dahulu."""
    if id(kon) in _NILAI_KATEGORI:
        return _NILAI_KATEGORI[id(kon)]
    daftar = []
    for t in TIPE_OBJEK.values():
        for p in t.kategori():
            for (v,) in kon.execute(f"SELECT DISTINCT {p.nama} FROM {t.id} WHERE {p.nama} <> ''"):
                if len(str(v)) >= 3:
                    daftar.append((_normal(str(v)), t.id, p.nama))
    daftar.sort(key=lambda x: -len(x[0]))
    _NILAI_KATEGORI[id(kon)] = daftar
    return daftar


def kenali_filter(kon: sqlite3.Connection, teks: str, tipe_dalam_jalur: set[str]) -> tuple[list[Filter], str]:
    """Tahun, nilai kategori, bendera asing/Indonesia, perbandingan angka sederhana."""
    filter_: list[Filter] = []
    sisa = f" {teks} "
    for cocok, tipe, kolom in nilai_kategori(kon):
        if tipe not in tipe_dalam_jalur:
            continue
        pola = re.compile(r"(?<!\w)" + re.escape(cocok) + r"(?!\w)")
        m = pola.search(sisa)
        if m:
            label = TIPE_OBJEK[tipe].properti_dict()[kolom].label.lower()
            filter_.append(Filter(tipe, kolom, "=", cocok, f"{TIPE_OBJEK[tipe].label} {label} = {cocok}"))
            sisa = sisa[:m.start()] + " " + sisa[m.end():]
    if "kapal" in tipe_dalam_jalur and re.search(r"\b(asing|luar negeri|foreign)\b", sisa) \
            and not any(f.tipe == "kapal" and f.kolom == "bendera" for f in filter_):
        filter_.append(Filter("kapal", "bendera", "<>", "Indonesia", "Kapal bendera ≠ Indonesia (asing)"))
    for m in re.finditer(r"\b(20\d\d)\b", sisa):
        tahun = m.group(1)
        for tipe in ("pelayaran", "insiden", "kapal", "perusahaan"):
            if tipe in tipe_dalam_jalur:
                kolom = KOLOM_TAHUN[tipe]
                label = TIPE_OBJEK[tipe].properti_dict()[kolom].label.lower()
                filter_.append(Filter(tipe, kolom, "tahun", tahun, f"{TIPE_OBJEK[tipe].label} {label} pada tahun {tahun}"))
                break
    m = re.search(r"\b(lebih dari|di atas|minimal|>=?|melebihi)\s*(\d[\d.]*)\s*(ribu|juta)?", sisa)
    if m:
        angka = _angka(m.group(2), m.group(3))
        for tipe, kolom in (("kapal", "dwt"), ("pelayaran", "muatan"), ("provinsi", "penduduk_juta"), ("insiden", "hari_tertahan")):
            if tipe in tipe_dalam_jalur:
                filter_.append(Filter(tipe, kolom, ">=", str(angka), f"{TIPE_OBJEK[tipe].label} {kolom} ≥ {angka:g}"))
                break
    m = re.search(r"\b(kurang dari|di bawah|maksimal|<=?)\s*(\d[\d.]*)\s*(ribu|juta)?", sisa)
    if m:
        angka = _angka(m.group(2), m.group(3))
        for tipe, kolom in (("kapal", "dwt"), ("pelayaran", "muatan"), ("provinsi", "penduduk_juta"), ("insiden", "hari_tertahan")):
            if tipe in tipe_dalam_jalur:
                filter_.append(Filter(tipe, kolom, "<=", str(angka), f"{TIPE_OBJEK[tipe].label} {kolom} ≤ {angka:g}"))
                break
    return filter_, sisa.strip()


def _angka(teks: str, pengali: str | None) -> float:
    n = float(teks.replace(".", ""))
    return n * {"ribu": 1_000, "juta": 1_000_000}.get(pengali or "", 1)


# ---------------------------------------------------------------------------
# 3. JALUR DI SKEMA
# ---------------------------------------------------------------------------
def semua_jalur(dari: str, ke: str, maks: int) -> list[list[str]]:
    """Semua jalur sederhana di graf skema dengan panjang <= maks (DFS)."""
    hasil: list[list[str]] = []

    def jelajah(jalur: list[str]) -> None:
        if len(jalur) - 1 > maks:
            return
        if jalur[-1] == ke and len(jalur) > 1:
            hasil.append(list(jalur))
            return
        for lanjut in ontologi.tetangga_tipe(jalur[-1]):
            if lanjut not in jalur or (lanjut == ke and lanjut == dari):
                jelajah(jalur + [lanjut])

    if dari == ke:
        return [[dari, ke]] if ontologi.tautan_antara(dari, ke) else []
    jelajah([dari])
    return hasil


def _ada_kata(kata: str, teks: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(kata) + r"(?!\w)", teks) is not None


def pilih_jalur(dari: str, ke: str, teks: str, sebutan_tipe: set[str],
                petunjuk_lokal: str = "") -> tuple[list[str], list[list[TipeTautan]]] | None:
    """Pilih jalur terbaik: pendek, tautannya cocok kata petunjuk, melewati tipe yang disebut dalam pertanyaan.

    Untuk langkah terakhir (yang menyentuh entitas), kata tepat sebelum entitas (`petunjuk_lokal`, misalnya "dari"
    atau "ke") lebih dipercaya daripada kata di seluruh kalimat; dengan begitu "dari Dumai ke Mundra" terbaca benar.
    """
    terpendek = ontologi.jalur_terpendek(dari, ke)
    if terpendek is None:
        return None
    if dari == ke:
        kandidat = [[dari, ke]]
    else:
        kandidat = semua_jalur(dari, ke, len(terpendek))   # terpendek + 1 lompatan
    terbaik, skor_terbaik = None, None
    for jalur in kandidat:
        tautan_per_langkah = []
        skor = -2 * (len(jalur) - 1)
        for i, (a, b) in enumerate(zip(jalur, jalur[1:])):
            pilihan = ontologi.tautan_antara(a, b)
            terakhir = i == len(jalur) - 2
            cocok: list[TipeTautan] = []
            tingkat = [teks]
            if terakhir and petunjuk_lokal:
                kata = petunjuk_lokal.split()
                tingkat = [kata[-1], " ".join(kata[-2:]), petunjuk_lokal, teks] if kata else [teks]
            for sumber_kata in tingkat:   # kata tepat sebelum entitas paling dipercaya, lalu melebar
                cocok = [l for l in pilihan if any(_ada_kata(k, sumber_kata) for k in l.kata_kunci)]
                if cocok:
                    break
            if cocok and len(pilihan) > 1:
                skor += 3
                pilihan = cocok
            elif cocok:
                skor += 1
            tautan_per_langkah.append(pilihan)
        skor += sum(1 for t in jalur[1:-1] if t in sebutan_tipe)
        if "pelayaran" in jalur[1:-1]:
            skor += 0.5   # kalau seri, data pergerakan nyata lebih informatif daripada relasi administratif
        if skor_terbaik is None or skor > skor_terbaik:
            terbaik, skor_terbaik = (jalur, tautan_per_langkah), skor
    return terbaik


# ---------------------------------------------------------------------------
# 4. PENYUSUN SQL
# ---------------------------------------------------------------------------
def _join_langkah(alias_dari: str, tipe_dari: str, alias_ke: str, tipe_ke: str, tautan: list[TipeTautan], teks: str,
                  nomor: str) -> str:
    """Klausa JOIN satu langkah; dibuat mudah dibaca kalau mungkin, UNION kalau tautannya campuran."""
    if tipe_dari == tipe_ke:  # tautan ke tipe sendiri: tentukan arah dari kata petunjuk
        l = tautan[0]
        ke_induk = any(k in teks for k in KATA_INDUK)
        ke_anak = any(k in teks for k in KATA_ANAK)
        if ke_anak and not ke_induk:      # "anak usaha X": target = anak, X = induknya
            return f"JOIN {tipe_ke} {alias_ke} ON {alias_ke}.id = {alias_dari}.{l.kolom_tujuan}"
        if ke_induk and not ke_anak:      # "induk dari X": target = induk, X = anaknya
            return f"JOIN {tipe_ke} {alias_ke} ON {alias_ke}.{l.kolom_tujuan} = {alias_dari}.id"
        return (f"JOIN {tipe_ke} {alias_ke} ON ({alias_ke}.id = {alias_dari}.{l.kolom_tujuan} "
                f"OR {alias_ke}.{l.kolom_tujuan} = {alias_dari}.id)")
    kolom_di_dari, kolom_di_ke, penghubung = [], [], []
    for l in tautan:
        if l.tabel == tipe_dari:
            kolom_di_dari.append(l.kolom_tujuan if l.sumber == tipe_dari else l.kolom_sumber)
        elif l.tabel == tipe_ke:
            kolom_di_ke.append(l.kolom_tujuan if l.sumber == tipe_ke else l.kolom_sumber)
        else:
            penghubung.append(l)
    if kolom_di_dari and not kolom_di_ke and not penghubung:
        syarat = f"{alias_ke}.id = {alias_dari}.{kolom_di_dari[0]}" if len(kolom_di_dari) == 1 else \
            f"{alias_ke}.id IN ({', '.join(alias_dari + '.' + k for k in kolom_di_dari)})"
        return f"JOIN {tipe_ke} {alias_ke} ON {syarat}"
    if kolom_di_ke and not kolom_di_dari and not penghubung:
        syarat = f"{alias_ke}.{kolom_di_ke[0]} = {alias_dari}.id" if len(kolom_di_ke) == 1 else \
            f"{alias_dari}.id IN ({', '.join(alias_ke + '.' + k for k in kolom_di_ke)})"
        return f"JOIN {tipe_ke} {alias_ke} ON {syarat}"
    if penghubung and len(tautan) == 1:
        l = penghubung[0]
        k_dari = l.kolom_sumber if l.sumber == tipe_dari else l.kolom_tujuan
        k_ke = l.kolom_tujuan if l.sumber == tipe_dari else l.kolom_sumber
        return (f"JOIN {l.tabel} r{nomor} ON r{nomor}.{k_dari} = {alias_dari}.id "
                f"JOIN {tipe_ke} {alias_ke} ON {alias_ke}.id = r{nomor}.{k_ke}")
    # campuran: satukan semua tautan sebagai relasi (dari, ke)
    bagian = []
    for l in tautan:
        k_dari = l.kolom_sumber if l.sumber == tipe_dari else l.kolom_tujuan
        k_ke = l.kolom_tujuan if l.sumber == tipe_dari else l.kolom_sumber
        bagian.append(f"SELECT {k_dari} AS dari, {k_ke} AS ke FROM {l.tabel}")
    return (f"JOIN ({' UNION ALL '.join(bagian)}) r{nomor} ON r{nomor}.dari = {alias_dari}.id "
            f"JOIN {tipe_ke} {alias_ke} ON {alias_ke}.id = r{nomor}.ke")


def _syarat_filter(f: Filter, alias: str) -> tuple[str, list]:
    if f.operator == "tahun":
        return f"CAST(substr({alias}.{f.kolom}, 1, 4) AS INTEGER) = ?", [int(f.nilai)]
    if f.operator == "=":
        return f"LOWER({alias}.{f.kolom}) = ?", [f.nilai.lower()]
    if f.operator == "<>":
        return f"{alias}.{f.kolom} <> ?", [f.nilai]
    return f"{alias}.{f.kolom} {f.operator} ?", [float(f.nilai)]


def susun_sql(r: Rencana, teks: str) -> None:
    """Isi r.sql dan r.params dari target, jalur, filter, maksud. Alias: a0 = target, a{k}_{i} = langkah ke-i jangkar k."""
    target = r.tipe_target
    assert target is not None
    join: list[str] = []
    where: list[str] = []
    params: list = []
    alias_tipe: dict[str, str] = {target: "a0"}   # tipe -> alias pertama yang mewakilinya
    for k, (e, jalur, tautan) in enumerate(zip(r.jangkar, r.jalur, r.tautan_jalur)):
        alias_sebelum = "a0"
        for i, (tipe_dari, tipe_ke) in enumerate(zip(jalur, jalur[1:])):
            alias_ke = f"a{k + 1}_{i + 1}"
            petunjuk = e.petunjuk if i == len(jalur) - 2 else teks
            join.append(_join_langkah(alias_sebelum, tipe_dari, alias_ke, tipe_ke, tautan[i], petunjuk + " " + teks, f"{k + 1}_{i + 1}"))
            alias_tipe.setdefault(tipe_ke, alias_ke)
            alias_sebelum = alias_ke
        if e.id:   # jangkar tanpa id = pivot keberadaan (cukup ada tautannya)
            where.append(f"{alias_sebelum}.id = ?")
            params.append(e.id)
    alias_ukur = None
    if r.maksud == "peringkat" and r.tipe_ukur:
        if r.tipe_ukur in alias_tipe:
            alias_ukur = alias_tipe[r.tipe_ukur]
        else:
            jalur = pilih_jalur(target, r.tipe_ukur, teks, set())
            if jalur:
                alias_sebelum = "a0"
                for i, (tipe_dari, tipe_ke) in enumerate(zip(jalur[0], jalur[0][1:])):
                    alias_ke = f"m{i + 1}"
                    join.append(_join_langkah(alias_sebelum, tipe_dari, alias_ke, tipe_ke, jalur[1][i], teks, f"m{i + 1}"))
                    alias_tipe.setdefault(tipe_ke, alias_ke)
                    alias_sebelum = alias_ke
                alias_ukur = alias_sebelum
    for f in r.filter:
        alias = alias_tipe.get(f.tipe)
        if alias is None:
            continue
        syarat, p = _syarat_filter(f, alias)
        where.append(syarat)
        params += p
    klausa_join = ("\n  " + "\n  ".join(join)) if join else ""
    klausa_where = ("\nWHERE " + "\n  AND ".join(where)) if where else ""
    inti = f"FROM {target} a0{klausa_join}{klausa_where}"
    judul = TIPE_OBJEK[target].kolom_judul
    if r.maksud == "hitung":
        ekstra = ", SUM(muatan) AS total_muatan" if target == "pelayaran" else ""
        r.sql = f"SELECT COUNT(*) AS jumlah{ekstra}\nFROM (SELECT DISTINCT a0.* {inti})"
    elif r.maksud == "peringkat" and alias_ukur:
        r.sql = (f"SELECT a0.*, COUNT(DISTINCT {alias_ukur}.id) AS jumlah\n{inti}\nGROUP BY a0.id\n"
                 f"ORDER BY jumlah DESC, a0.{judul}\nLIMIT {BATAS_PERINGKAT}")
    elif r.maksud == "ekstrem" and r.urut:
        kolom, arah = r.urut
        r.sql = f"SELECT DISTINCT a0.*\n{inti}\nORDER BY a0.{kolom} {arah}, a0.{judul}\nLIMIT {BATAS_PERINGKAT}"
    else:
        r.sql = f"SELECT DISTINCT a0.*\n{inti}\nORDER BY a0.{judul}\nLIMIT {BATAS_DAFTAR}"
    r.params = params


# ---------------------------------------------------------------------------
# 5. PERENCANA UTAMA
# ---------------------------------------------------------------------------
def _sinonim(tipe: str) -> set[str]:
    t = TIPE_OBJEK[tipe]
    return set(t.sinonim) | {t.label.lower(), t.label_jamak.lower()}


def rencanakan(kon: sqlite3.Connection, pertanyaan: str, konteks: list[Entitas] | None = None) -> Rencana:
    r = Rencana(pertanyaan)
    teks = _normal(pertanyaan)
    entitas, sisa = kenali_entitas(kon, teks)
    # rujukan ke percakapan sebelumnya: "kapal itu", "pelabuhan tersebut", "yang sama"
    if not entitas and konteks and any(_ada_kata(k, sisa) for k in KATA_RUJUK):
        entitas = [Entitas(e.tipe, e.id, e.nama, e.teks, 0, "") for e in konteks]
        r.catatan = "Memakai objek dari pertanyaan sebelumnya: " + ", ".join(e.nama for e in entitas)
    # kata tipe tepat sebelum entitas bertipe sama hanya penjelas ("pelabuhan Balikpapan", "kapal Celebes Sentosa"),
    # bukan target; buang satu kemunculannya supaya tidak terhitung
    for e in entitas:
        kata_sebelum = e.petunjuk.split()[-1] if e.petunjuk.split() else ""
        if kata_sebelum and kata_sebelum in _sinonim(e.tipe):
            sisa = re.sub(r"(?<!\w)" + re.escape(kata_sebelum) + r"(?!\w)", " ", sisa, count=1)
            sisa = re.sub(r"\s+", " ", sisa).strip()
    sebutan = kenali_tipe(sisa)
    kata_sisa = sisa.split()
    tipe_disebut: list[str] = []
    for pos, tipe, s in sebutan:
        if tipe not in tipe_disebut:
            tipe_disebut.append(tipe)
    # target = tipe yang diikuti kata tanya/penghubung ("pelabuhan mana", "perusahaan dengan"), kalau tidak ada: tipe pertama
    for pos, tipe, s in sebutan:
        berikut = kata_sisa[pos + len(s.split())] if pos + len(s.split()) < len(kata_sisa) else ""
        if berikut in ("mana", "apa", "yang", "dengan", "saja", "manakah", "apakah"):
            tipe_disebut.remove(tipe)
            tipe_disebut.insert(0, tipe)
            break
    maksud = "daftar"
    if any(_ada_kata(k, sisa) for k in KATA_PERINGKAT):
        maksud = "peringkat"
    elif any(_ada_kata(k, sisa) for k in KATA_HITUNG):
        maksud = "hitung"
    urut = None
    for kata, tipe, kolom, arah in SUPERLATIF_PROPERTI:
        if _ada_kata(kata, sisa) and (tipe in tipe_disebut or (not tipe_disebut and entitas)):
            if maksud != "peringkat":
                maksud, urut = "ekstrem", (kolom, arah)
                if tipe not in tipe_disebut:
                    tipe_disebut.insert(0, tipe)
                elif tipe_disebut[0] != tipe and f"{tipe} {kata}" not in sisa and not any(
                        _ada_kata(f"{s} {kata}", sisa) for s in _sinonim(tipe)):
                    pass
                break
    if not tipe_disebut:
        if _ada_kata("siapa", sisa) and entitas:
            tipe_disebut = ["perusahaan"]
        elif len(entitas) >= 2 and all(e.tipe == "pelabuhan" for e in entitas):
            tipe_disebut = ["pelayaran"]      # "dari Dumai ke Mundra" tanpa kata benda = pelayaran
        elif maksud in ("hitung", "peringkat") and entitas:
            tipe_disebut = ["pelayaran"]
    if not tipe_disebut and entitas:
        r.maksud, r.jangkar = "detail", entitas[:1]
        r.penjelasan = [f"Menampilkan objek {TIPE_OBJEK[entitas[0].tipe].label} «{entitas[0].nama}» beserta tautannya."]
        return r
    if not tipe_disebut:
        r.maksud = "bantuan"
        return r
    target = tipe_disebut[0]
    r.tipe_target, r.maksud, r.urut = target, maksud, urut
    if maksud == "peringkat":
        kandidat_ukur = [t for t in tipe_disebut[1:] if t != target]
        r.tipe_ukur = kandidat_ukur[0] if kandidat_ukur else ("pelayaran" if target != "pelayaran" else "insiden")
        if target == "pelayaran" and not kandidat_ukur:
            # "pelayaran terbanyak" tanpa tipe lain tidak bermakna; ubah menjadi hitung
            r.maksud, r.tipe_ukur = "hitung", None
    # jangkar: entitas yang bertipe lain dari target, atau bertipe sama kalau ada tautan ke diri sendiri
    for e in entitas:
        if e.tipe == target and not ontologi.tautan_antara(target, target):
            continue
        hasil = pilih_jalur(target, e.tipe, teks, set(tipe_disebut), e.petunjuk)
        if hasil is None:
            continue
        r.jangkar.append(e)
        r.jalur.append(hasil[0])
        r.tautan_jalur.append(hasil[1])
    # pivot keberadaan: tipe lain yang disebut tanpa nama objek ("kapal yang pernah mengalami insiden") ikut di-join,
    # supaya filter pada tipe itu ("insiden tingkat tinggi", "kapal asing") bisa diterapkan
    for tipe in tipe_disebut[1:]:
        if tipe == target or tipe == r.tipe_ukur or any(e.tipe == tipe for e in r.jangkar):
            continue
        hasil = pilih_jalur(target, tipe, teks, set(tipe_disebut))
        if hasil is None:
            continue
        r.jangkar.append(Entitas(tipe, "", TIPE_OBJEK[tipe].label_jamak, "", 0, ""))
        r.jalur.append(hasil[0])
        r.tautan_jalur.append(hasil[1])
    tipe_dalam_jalur = {target} | {t for j in r.jalur for t in j} | ({r.tipe_ukur} if r.tipe_ukur else set())
    r.filter, _ = kenali_filter(kon, sisa, tipe_dalam_jalur)
    susun_sql(r, teks)
    r.penjelasan = jelaskan(r)
    return r


def jelaskan(r: Rencana) -> list[str]:
    t = TIPE_OBJEK[r.tipe_target]
    baris = []
    nama_maksud = {"daftar": "Daftar", "hitung": "Hitung jumlah", "peringkat": "Peringkat", "ekstrem": "Urutkan"}[r.maksud]
    baris.append(f"**Himpunan objek:** {t.ikon} {t.label_jamak} ({nama_maksud})")
    for e, jalur, tautan in zip(r.jangkar, r.jalur, r.tautan_jalur):
        langkah = [f"{t.ikon} {t.label}"]
        for (a, b), pilihan in zip(zip(jalur, jalur[1:]), tautan):
            label = " / ".join(l.label_dari(a) for l in pilihan)
            langkah.append(f"—{label}→ {TIPE_OBJEK[b].ikon} {TIPE_OBJEK[b].label}")
        baris.append(f"**Pivot:** {' '.join(langkah)}" + (f" = «{e.nama}»" if e.id else " (harus ada)"))
    if r.maksud == "peringkat" and r.tipe_ukur:
        baris.append(f"**Diurutkan menurut:** jumlah {TIPE_OBJEK[r.tipe_ukur].label_jamak.lower()} terkait")
    if r.maksud == "ekstrem" and r.urut:
        kolom, arah = r.urut
        baris.append(f"**Diurutkan menurut:** {t.properti_dict()[kolom].label} ({'menurun' if arah == 'DESC' else 'menaik'})")
    for f in r.filter:
        baris.append(f"**Filter:** {f.label}")
    if r.catatan:
        baris.append(f"_{r.catatan}_")
    return baris


# ---------------------------------------------------------------------------
# 6. EKSEKUSI + KALIMAT JAWABAN
# ---------------------------------------------------------------------------
def _angka_id(n) -> str:
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(n):,}".replace(",", ".")


def jalankan(kon: sqlite3.Connection, r: Rencana) -> tuple[pd.DataFrame, str]:
    """Jalankan SQL rencana dan susun kalimat jawaban dalam bahasa Indonesia."""
    if r.maksud in ("bantuan", "detail"):
        return pd.DataFrame(), ""
    df = basis_data.sql_df(kon, r.sql, r.params)
    t = TIPE_OBJEK[r.tipe_target]
    syarat = ""
    bernama = [e for e in r.jangkar if e.id]
    if bernama:
        syarat = " yang terkait dengan " + " dan ".join(f"{TIPE_OBJEK[e.tipe].label.lower()} «{e.nama}»" for e in bernama)
    tanpa_nama = [e for e in r.jangkar if not e.id]
    if tanpa_nama:
        syarat += " yang punya " + " dan ".join(TIPE_OBJEK[e.tipe].label_jamak.lower() for e in tanpa_nama)
    if r.filter:
        syarat += " (" + "; ".join(f.label.lower() for f in r.filter) + ")"
    if r.maksud == "hitung":
        n = int(df.iloc[0]["jumlah"]) if not df.empty else 0
        kalimat = f"Ada **{_angka_id(n)} {t.label_jamak.lower()}**{syarat}."
        if r.tipe_target == "pelayaran" and n and pd.notna(df.iloc[0].get("total_muatan")):
            kalimat += f" Total muatan **{_angka_id(df.iloc[0]['total_muatan'])} ton**."
        return df, kalimat
    if df.empty:
        return df, f"Tidak ada {t.label_jamak.lower()}{syarat}."
    judul = t.kolom_judul
    if r.maksud == "peringkat":
        ukur = TIPE_OBJEK[r.tipe_ukur].label_jamak.lower() if r.tipe_ukur else "objek"
        atas = "; ".join(f"**{row[judul]}** ({_angka_id(row['jumlah'])})" for _, row in df.head(3).iterrows())
        return df, f"{t.label} dengan {ukur} terbanyak{syarat}: {atas}."
    if r.maksud == "ekstrem" and r.urut:
        kolom, _ = r.urut
        p = t.properti_dict()[kolom]
        atas = "; ".join(f"**{row[judul]}** ({_angka_id(row[kolom])} {p.satuan})".replace(" )", ")")
                         for _, row in df.head(3).iterrows())
        return df, f"{t.label_jamak} diurutkan menurut {p.label.lower()}{syarat}: {atas}."
    n = len(df)
    batas = f" (ditampilkan {BATAS_DAFTAR} pertama)" if n >= BATAS_DAFTAR else ""
    contoh = ", ".join(str(x) for x in df[judul].head(5))
    return df, f"Ditemukan **{_angka_id(n)} {t.label_jamak.lower()}**{syarat}{batas}: {contoh}{'…' if n > 5 else ''}."


CONTOH_PERTANYAAN = [
    "Kapal apa saja yang dimiliki Nusantara Bulk Carriers?",
    "Komoditas apa yang berangkat dari Balikpapan?",
    "Berapa pelayaran yang tiba di Tanjung Priok tahun 2025?",
    "Pelabuhan mana yang paling banyak pelayaran?",
    "Perusahaan dengan kapal terbanyak",
    "Kapal berbendera asing mana yang mengangkut nikel?",
    "Siapa pemilik kapal Celebes Sentosa 8?",
    "Kapal tertua yang pernah mengalami insiden tingkat tinggi",
    "Pelayaran dari Dumai ke Mundra",
    "Provinsi penghasil batu bara",
    "Anak usaha Khatulistiwa Group",
    "Pelabuhan di Kalimantan Timur",
    "Insiden di Tanjung Perak tahun 2026",
    "Tanjung Priok",
]
